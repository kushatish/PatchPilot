from pathlib import Path
from dataclasses import asdict
import json
import pytest
from agent.llm_client import MockLLMClient, _make_unified_diff, _safe_json
from agent.orchestrator import IssueResolverAgent
from agent.repo_manager import RepoManager
from agent.patch_generator import apply_patch
from agent.test_runner import TestResult as Result, build_command, run_tests
from agent.artifacts import write_artifacts
from agent.github_client import GitHubClient
from cli import main


def make_agent(tmp_path, client=None, **kwargs):
    return IssueResolverAgent(client or MockLLMClient(),
                              repo_manager=RepoManager(str(tmp_path / 'work')), backend='local', **kwargs)


def test_demo_proves_regression_and_full_suite(tmp_path):
    agent = make_agent(tmp_path)
    try:
        report = agent.run(demo=True)
        assert report.status == 'fixed'
        assert report.baseline_tests.failed == 2
        assert report.regression_before.reproduced
        assert report.regression_after.passed == 2
        assert report.post_patch_tests.passed == 5
        folder = write_artifacts(report, tmp_path / 'output')
        second = write_artifacts(report, tmp_path / 'output')
        assert folder != second
        assert json.loads((folder / 'report.json').read_text())['status'] == 'fixed'
        assert (folder / 'patch.diff').read_text() == report.diff
        assert 'test_whitespace_date' in (folder / 'test_patchpilot_regression.py').read_text()
    finally:
        agent.cleanup()


class RetryClient(MockLLMClient):
    def __init__(self):
        self.calls = 0
        self.feedback = ''

    def generate_patch(self, issue_text, code_context, test_output):
        self.calls += 1
        self.feedback = test_output
        if self.calls == 1:
            original = code_context['csv_parser.py']
            # Applies successfully, but does not repair the bug.
            return {'diff': _make_unified_diff('csv_parser.py', original,
                    original.replace('A tiny CSV utility', 'A small CSV utility')), 'reasoning': 'Wrong fix'}
        assert 'Previous candidate' in test_output
        return super().generate_patch(issue_text, code_context, test_output)


def test_retry_uses_failure_and_resets_original_source(tmp_path):
    client = RetryClient()
    agent = make_agent(tmp_path, client)
    try:
        report = agent.run(demo=True)
        assert report.status == 'fixed'
        assert len(report.attempts) == 2
        assert '2 failed' in report.attempts[0]['regression']
        assert 'A tiny CSV utility' in (Path(report.repo_path) / 'csv_parser.py').read_text()
    finally:
        agent.cleanup()


class PassingRegression(MockLLMClient):
    def generate_regression_test(self, issue_text, code_context):
        return {'code': 'def test_already_passes():\n    assert True\n'}


def test_passing_regression_blocks_patch_generation(tmp_path):
    agent = make_agent(tmp_path, PassingRegression())
    try:
        report = agent.run(demo=True)
        assert report.status == 'no_repro'
        assert not report.attempts
    finally:
        agent.cleanup()


def test_exhaustion_restores_baseline(tmp_path):
    client = RetryClient()
    agent = make_agent(tmp_path, client, max_attempts=1)
    try:
        report = agent.run(demo=True)
        assert report.status == 'patch_failed'
        assert not report.diff
        assert 'A tiny CSV utility' in (Path(report.repo_path) / 'csv_parser.py').read_text()
    finally:
        agent.cleanup()


@pytest.mark.parametrize('path', ['../escape.py', 'tests/test_existing.py', 'conftest.py'])
def test_patch_scope_rejects_unapproved_paths(tmp_path, path):
    diff = f'--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-old\n+new\n'
    result = apply_patch(str(tmp_path), diff, {'source.py'})
    assert not result.applied
    assert 'approved' in result.message


def test_symlink_patch_is_rejected(tmp_path):
    outside = tmp_path.parent / 'outside.py'
    outside.write_text('old\n')
    (tmp_path / 'source.py').symlink_to(outside)
    diff = _make_unified_diff('source.py', 'old\n', 'new\n')
    assert not apply_patch(str(tmp_path), diff, {'source.py'}).applied
    assert outside.read_text() == 'old\n'


def test_no_tests_is_not_success():
    assert not Result(returncode=0).all_passed
    assert not Result(failed=1, errors=1, returncode=1).reproduced
    assert not Result(failed=1, returncode=2).reproduced


def test_docker_command_is_restricted(tmp_path):
    cmd = build_command(str(tmp_path), backend='docker', name='test')
    for flag in ['--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                 '--user=65534:65534', '--pull=never', '--memory=512m']:
        assert flag in cmd
    assert any('dst=/repo,readonly' in item for item in cmd)
    assert '--privileged' not in cmd


def test_timeout_decodes_partial_output(monkeypatch, tmp_path):
    import subprocess
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('pytest', 1, output=b'partial', stderr=b'failure')
    monkeypatch.setattr(subprocess, 'run', timeout)
    result = run_tests(str(tmp_path))
    assert result.timed_out
    assert result.raw_output == 'partialfailure'


def test_real_run_requires_key(monkeypatch, tmp_path):
    import config
    monkeypatch.setattr(config, 'ANTHROPIC_API_KEY', '')
    assert main(['--repo', 'owner/repo', '--issue', '1', '--output', str(tmp_path)]) == 1


@pytest.mark.parametrize('slug', ['https://evil.example/owner/repo', '../repo', 'owner/repo/extra'])
def test_github_slug_validation(slug):
    with pytest.raises(ValueError):
        GitHubClient.parse_repo_slug(slug)


def test_safe_json_rejects_non_object():
    assert _safe_json('[]', {'diff': ''}) == {'diff': ''}


class InvalidPatchClient(MockLLMClient):
    def generate_patch(self, issue_text, code_context, test_output):
        return {'diff': 'not a diff', 'reasoning': 'Malformed'}


def test_patch_application_failures_are_recorded_and_bounded(tmp_path):
    agent = make_agent(tmp_path, InvalidPatchClient(), max_attempts=2)
    try:
        report = agent.run(demo=True)
        assert report.status == 'patch_failed'
        assert len(report.attempts) == 2
        assert all(not attempt['applied'] for attempt in report.attempts)
    finally:
        agent.cleanup()


def test_docker_timeout_attempts_container_cleanup(monkeypatch, tmp_path):
    import subprocess
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ['docker', 'run']:
            raise subprocess.TimeoutExpired(cmd, 1, output=b'partial')
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(subprocess, 'run', fake_run)
    result = run_tests(str(tmp_path), backend='docker')
    assert result.timed_out
    assert calls[1][:3] == ['docker', 'rm', '-f']
    assert calls[0][calls[0].index('--name') + 1] == calls[1][-1]
