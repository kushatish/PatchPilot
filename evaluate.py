#!/usr/bin/env python3
"""Evaluate a user-selected issue manifest without publishing any changes."""
import argparse
import json
from pathlib import Path
from agent.artifacts import write_artifacts
from agent.llm_client import get_llm_client
from agent.orchestrator import IssueResolverAgent
import config


def main():
    parser = argparse.ArgumentParser(description='Measure repair outcomes; --demo measures only the predefined fixture')
    parser.add_argument('manifest', nargs='?', help='JSON list of {repo, issue} cases')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--execution', choices=['local', 'docker'], default='docker')
    parser.add_argument('--docker-image', default='patchpilot-tests:local')
    parser.add_argument('--max-attempts', type=int, choices=range(1, 6), default=3)
    parser.add_argument('--input-price', type=float, help='USD per million input tokens')
    parser.add_argument('--output-price', type=float, help='USD per million output tokens')
    args = parser.parse_args()
    if (args.input_price is None) != (args.output_price is None):
        parser.error('Supply both token prices or neither')
    if any(p is not None and p < 0 for p in (args.input_price, args.output_price)):
        parser.error('Prices cannot be negative')
    if not args.demo and not args.manifest:
        parser.error('Supply an issue manifest or --demo')
    cases = [{}] if args.demo else json.loads(Path(args.manifest).read_text())
    if not isinstance(cases, list) or not cases:
        parser.error('Manifest must contain at least one case')
    results = []
    for case in cases:
        if not args.demo and (not isinstance(case, dict) or not case.get('repo') or not isinstance(case.get('issue'), int) or case['issue'] < 1):
            parser.error('Each case needs repo and a positive integer issue')
        agent = IssueResolverAgent(get_llm_client(force_mock=args.demo), max_attempts=args.max_attempts,
                                   backend='local' if args.demo else args.execution, image=args.docker_image)
        try:
            report = agent.run(case.get('repo'), case.get('issue'), args.demo, ref=case.get('ref'))
            if args.input_price is not None:
                report.estimated_cost_usd = round((report.input_tokens * args.input_price + report.output_tokens * args.output_price) / 1_000_000, 6)
            folder = write_artifacts(report, config.OUTPUT_DIR)
            results.append({'case': case, 'status': report.status, 'seconds': report.elapsed_seconds,
                            'attempts': len(report.attempts), 'input_tokens': report.input_tokens,
                            'output_tokens': report.output_tokens, 'estimated_cost_usd': report.estimated_cost_usd, 'artifacts': str(folder.resolve())})
        finally:
            agent.cleanup()
    summary = {'mode': 'mock_demo' if args.demo else 'real_issues', 'cases': len(results),
               'verified_candidates': sum(r['status'] == 'fixed' for r in results),
               'candidate_success_rate': sum(r['status'] == 'fixed' for r in results) / len(results),
               'total_estimated_cost_usd': sum(r['estimated_cost_usd'] for r in results) if args.input_price is not None else None,
               'results': results}
    # Store beside the last run, avoiding a shared filename across evaluations.
    target = folder / 'evaluation.json'
    target.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if all(r['status'] == 'fixed' for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
