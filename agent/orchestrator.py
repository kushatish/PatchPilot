"""Evidence-first issue repair with bounded, independent candidate attempts."""
import ast
import os
import time
from pathlib import Path
from dataclasses import dataclass, field

import config
from agent import code_search, patch_generator, test_runner
from agent.github_client import GitHubClient, Issue
from agent.llm_client import LLMClient
from agent.repo_manager import RepoManager


@dataclass
class RunReport:
    issue: Issue = None
    classification: dict = field(default_factory=dict)
    keywords: list = field(default_factory=list)
    file_matches: list = field(default_factory=list)
    inspected_files: list = field(default_factory=list)
    test_files_run: list = field(default_factory=list)
    baseline_tests: test_runner.TestResult = None
    diff: str = ""
    patch_reasoning: str = ""
    patch_applied: bool = False
    patch_message: str = ""
    post_patch_tests: test_runner.TestResult = None
    explanation: str = ""
    repo_path: str = ""
    status: str = "incomplete"  # incomplete | fixed | patch_failed | no_repro | error
    log: list = field(default_factory=list)
    regression_code: str = ""
    regression_reasoning: str = ""
    regression_before: test_runner.TestResult = None
    regression_after: test_runner.TestResult = None
    attempts: list = field(default_factory=list)
    elapsed_seconds: float = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = None
    backend: str = "local"
    base_commit: str = ""
    repo_slug: str = ""
    error: str = ""
    checkout_ref: str = ""
    docker_image: str = "patchpilot-tests:local"

    def step(self, msg: str):
        self.log.append(msg)
        print(f"[agent] {msg}")



class IssueResolverAgent:
    def __init__(self, llm_client, github_client=None, repo_manager=None,
                 max_attempts=3, backend='docker', image='patchpilot-tests:local'):
        if not 1 <= max_attempts <= 5:
            raise ValueError('max_attempts must be between 1 and 5')
        self.llm = llm_client
        self.github = github_client or GitHubClient()
        self.repo_manager = repo_manager or RepoManager()
        self.max_attempts = max_attempts
        self.backend = backend
        self.image = image

    def _test(self, repo, paths=None):
        return test_runner.run_tests(repo, paths, self.backend, self.image)

    def run(self, repo_slug=None, issue_number=None, demo=False, ref=None, fixture_path=None):
        started = time.monotonic()
        before_tokens = (getattr(self.llm, 'input_tokens', 0), getattr(self.llm, 'output_tokens', 0))
        report = RunReport(backend=self.backend, repo_slug=repo_slug or '', checkout_ref=ref or '', docker_image=self.image)
        try:
            self._resolve(report, repo_slug, issue_number, demo, ref, fixture_path)
        except Exception as exc:
            report.status = 'error'
            report.error = str(exc)
            report.step(f'Error: {exc}')
        finally:
            report.elapsed_seconds = round(time.monotonic() - started, 3)
            report.input_tokens = getattr(self.llm, 'input_tokens', 0) - before_tokens[0]
            report.output_tokens = getattr(self.llm, 'output_tokens', 0) - before_tokens[1]
        return report

    def _resolve(self, report, repo_slug, issue_number, demo, ref, fixture_path):
        import subprocess
        fixture = Path(fixture_path) if fixture_path else Path(__file__).resolve().parent.parent / 'demo_repo'
        report.step('Loading issue and classifying it')
        report.issue = (self.github.load_demo_issue(str(fixture)) if demo
                        else self.github.fetch_issue(repo_slug, issue_number))
        report.classification = self.llm.classify_issue(report.issue.full_text)
        report.repo_path = (self.repo_manager.copy_demo_repo(str(fixture)) if demo
                            else self.repo_manager.clone(repo_slug, ref=ref))
        root = Path(report.repo_path)
        report.base_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        report.keywords = code_search.extract_keywords(report.issue.title, report.issue.body)
        report.file_matches = code_search.search_repository(str(root), report.keywords)
        if not report.file_matches:
            report.status = 'no_repro'
            report.step('No relevant source files found')
            return
        context = code_search.expand_import_context(str(root),
            code_search.read_relevant_files(str(root), report.file_matches))
        report.inspected_files = list(context)
        report.step(f'Inspected files: {report.inspected_files}')
        report.step('Running the full baseline suite')
        report.baseline_tests = self._test(str(root))
        if report.baseline_tests.timed_out or report.baseline_tests.errors or report.baseline_tests.returncode not in (0, 1):
            report.status = 'test_error'
            report.step('Baseline environment or collection failed; refusing to patch')
            return
        report.step('Generating a regression test before generating the fix')
        regression = self.llm.generate_regression_test(report.issue.full_text, context)
        report.regression_code = regression.get('code', '')
        report.regression_reasoning = regression.get('reasoning', '')
        tree = ast.parse(report.regression_code)
        if not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith('test_')
                   for n in ast.walk(tree)):
            raise ValueError('Generated regression contains no test function')
        if any(isinstance(n, ast.Attribute) and n.attr in ('skip', 'skipif', 'xfail') for n in ast.walk(tree)):
            raise ValueError('Regression cannot skip or xfail')
        test_path = root / 'test_patchpilot_regression.py'
        if test_path.exists():
            raise ValueError('Reserved regression test filename already exists')
        test_path.write_text(report.regression_code)
        report.test_files_run = ['test_patchpilot_regression.py', '<full suite>']
        report.regression_before = self._test(str(root), ['test_patchpilot_regression.py'])
        if not report.regression_before.reproduced:
            report.status = 'no_repro'
            report.step('Generated test did not fail cleanly; no source changes attempted')
            return
        report.step(f'Regression reproduced: {report.regression_before.summary}')
        allowed = {path for path in context if Path(path).suffix == '.py'
                   and not Path(path).name.startswith('test_')
                   and not Path(path).name.endswith('_test.py')
                   and Path(path).name != 'conftest.py' and 'tests' not in Path(path).parts}
        # Every attempt starts from identical original source. Tests cannot be edited by patches.
        originals = {path: (root / path).read_bytes() for path in allowed}
        feedback = report.baseline_tests.raw_output + '\nREGRESSION:\n' + report.regression_before.raw_output
        for number in range(1, self.max_attempts + 1):
            for path, content in originals.items():
                (root / path).write_bytes(content)
            test_path.write_text(report.regression_code)
            report.step(f'Generating candidate {number}/{self.max_attempts}')
            candidate = self.llm.generate_patch(report.issue.full_text, context, feedback)
            diff = candidate.get('diff', '')
            applied = patch_generator.apply_patch(str(root), diff, allowed)
            attempt = {'number': number, 'diff': diff, 'reasoning': candidate.get('reasoning', ''),
                       'applied': applied.applied, 'message': applied.message}
            report.attempts.append(attempt)
            report.patch_message = applied.message
            if not applied.applied:
                feedback = report.regression_before.raw_output + '\nPrevious candidate:\n' + str(diff) + '\nApplication failure:\n' + applied.message
                continue
            report.regression_after = self._test(str(root), ['test_patchpilot_regression.py'])
            report.post_patch_tests = self._test(str(root))
            attempt['regression'] = report.regression_after.summary
            attempt['suite'] = report.post_patch_tests.summary
            if report.regression_after.all_passed and report.post_patch_tests.all_passed:
                report.diff = diff
                report.patch_reasoning = attempt['reasoning']
                report.patch_applied = True
                report.status = 'fixed'
                report.step('Regression and full suite pass; candidate is ready for review')
                try:
                    report.explanation = self.llm.explain_patch(diff, report.issue.full_text)
                except Exception as exc:
                    report.explanation = report.patch_reasoning
                    report.step(f'Explanation unavailable: {exc}')
                return
            feedback = (report.regression_before.raw_output + '\nPrevious candidate:\n' + diff
                        + '\nRegression failure:\n' + report.regression_after.raw_output
                        + '\nFull suite:\n' + report.post_patch_tests.raw_output
                        + '\nGenerate a new patch against the ORIGINAL supplied files, not the previous candidate.')
        for path, content in originals.items():
            (root / path).write_bytes(content)
        report.status = 'patch_failed'
        report.step('Attempt limit reached; source restored to baseline')

    def cleanup(self):
        self.repo_manager.cleanup()
