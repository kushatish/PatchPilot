#!/usr/bin/env python3
"""Three transparent synthetic cases; recorded replay by default, real Claude with --ai."""
import argparse
import json
import tempfile
from pathlib import Path
from agent.llm_client import MockLLMClient, get_llm_client, _make_unified_diff
from agent.orchestrator import IssueResolverAgent
from agent.artifacts import write_artifacts
from agent.test_runner import run_tests
import config

CASES = [
    {'name': 'empty-average', 'module': 'stats',
     'issue': 'average crashes on an empty list; average([]) should return 0.',
     'source': 'def average(values):\n    return sum(values) / len(values)\n',
     'fixed': 'def average(values):\n    return sum(values) / len(values) if values else 0\n',
     'baseline': 'from stats import average\ndef test_regular():\n    assert average([2, 4]) == 3\n',
     'regression': 'from stats import average\ndef test_empty():\n    assert average([]) == 0\n',
     'holdout': 'from stats import average\ndef test_negative():\n    assert average([-4, -2]) == -3\ndef test_single():\n    assert average([7]) == 7\n'},
    {'name': 'whitespace-slug', 'module': 'slugger',
     'issue': 'slugify should trim outer whitespace and collapse repeated whitespace into one hyphen.',
     'source': "def slugify(text):\n    return text.lower().replace(' ', '-')\n",
     'fixed': "def slugify(text):\n    return '-'.join(text.lower().split())\n",
     'baseline': "from slugger import slugify\ndef test_regular():\n    assert slugify('Hello World') == 'hello-world'\n",
     'regression': "from slugger import slugify\ndef test_spaces():\n    assert slugify('  Hello   World  ') == 'hello-world'\n",
     'holdout': "from slugger import slugify\ndef test_tabs():\n    assert slugify('One\\tTwo') == 'one-two'\ndef test_blank():\n    assert slugify('   ') == ''\n"},
    {'name': 'inclusive-clamp', 'module': 'bounds',
     'issue': 'clamp should include the upper bound: clamp(12, 0, 10) should return 10, not 9.',
     'source': 'def clamp(value, lower, upper):\n    return min(max(value, lower), upper - 1)\n',
     'fixed': 'def clamp(value, lower, upper):\n    return min(max(value, lower), upper)\n',
     'baseline': 'from bounds import clamp\ndef test_regular():\n    assert clamp(5, 0, 10) == 5\n',
     'regression': 'from bounds import clamp\ndef test_upper():\n    assert clamp(12, 0, 10) == 10\n',
     'holdout': 'from bounds import clamp\ndef test_lower():\n    assert clamp(-2, 0, 10) == 0\ndef test_exact():\n    assert clamp(10, 0, 10) == 10\n'}
]


class RecordedClient(MockLLMClient):
    """Authored responses, not a simulated measurement of model intelligence."""
    def __init__(self, case):
        self.case = case

    def classify_issue(self, text):
        return {'category': 'bug', 'component': self.case['module'], 'summary': self.case['issue']}

    def generate_regression_test(self, text, context):
        return {'code': self.case['regression'], 'reasoning': 'Authored benchmark reproducer'}

    def generate_patch(self, text, context, feedback):
        path = self.case['module'] + '.py'
        return {'diff': _make_unified_diff(path, context[path], self.case['fixed']),
                'reasoning': 'Authored benchmark reference repair'}

    def explain_patch(self, diff, text):
        return 'Recorded reference repair: ' + self.case['issue']


def run_case(case, output, ai=False, backend='local', image='patchpilot-tests:local'):
    with tempfile.TemporaryDirectory() as folder:
        fixture = Path(folder)
        (fixture / (case['module'] + '.py')).write_text(case['source'])
        (fixture / 'test_existing.py').write_text(case['baseline'])
        (fixture / 'ISSUE.md').write_text('Title: ' + case['name'] + '\n\nBody:\n' + case['issue'])
        client = get_llm_client() if ai else RecordedClient(case)
        agent = IssueResolverAgent(client, backend=backend, image=image)
        try:
            report = agent.run(demo=True, fixture_path=fixture)
            holdout = None
            if report.status == 'fixed':
                # Independent tests were never provided to the generation backend.
                (Path(report.repo_path) / 'test_independent_holdout.py').write_text(case['holdout'])
                holdout = run_tests(report.repo_path, ['test_independent_holdout.py'], backend, image)
            artifact = write_artifacts(report, output)
            if holdout:
                (artifact / 'holdout.json').write_text(json.dumps({
                    'passed': holdout.all_passed, 'summary': holdout.summary, 'output': holdout.raw_output}, indent=2))
            return {'case': case['name'], 'status': report.status,
                    'regression_reproduced': bool(report.regression_before and report.regression_before.reproduced),
                    'holdout_passed': bool(holdout and holdout.all_passed),
                    'attempts': len(report.attempts), 'seconds': report.elapsed_seconds,
                    'input_tokens': report.input_tokens, 'output_tokens': report.output_tokens,
                    'artifacts': str(artifact)}
        finally:
            agent.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ai', action='store_true', help='Use actual Claude; API key required')
    parser.add_argument('--execution', choices=['local', 'docker'])
    parser.add_argument('--docker-image', default='patchpilot-tests:local')
    parser.add_argument('--output', default=config.OUTPUT_DIR)
    args = parser.parse_args()
    backend = args.execution or ('docker' if args.ai else 'local')
    results = [run_case(case, args.output, args.ai, backend, args.docker_image) for case in CASES]
    successful = sum(r['status'] == 'fixed' and r['holdout_passed'] for r in results)
    summary = {'mode': 'claude_synthetic' if args.ai else 'recorded_replay',
               'synthetic_cases': len(results), 'verified_with_holdout': successful,
               'rate': successful / len(results), 'results': results,
               'limitation': 'Recorded replay validates workflow only. Synthetic AI evaluation is not real-world issue performance.'}
    target = Path(results[-1]['artifacts']) / 'benchmark.json'
    target.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if successful == len(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
