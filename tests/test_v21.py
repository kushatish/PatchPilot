from pathlib import Path
import json
import sys
import pytest
from agent.code_search import FileMatch, read_relevant_files
from agent.repo_manager import RepoManager
from agent.test_runner import TestResult as Result
import publish_pr
from benchmark import CASES, run_case


def test_large_file_context_keeps_named_definition(tmp_path):
    source = '# padding\n' * 900 + 'def broken_parser(value):\n    return value\n'
    (tmp_path / 'parser.py').write_text(source)
    context = read_relevant_files(str(tmp_path), [FileMatch('parser.py', 1, {'broken_parser'})])
    assert 'def broken_parser' in context['parser.py']
    assert len(context['parser.py']) <= 6000


def test_git_ref_is_forwarded_without_shell(tmp_path, monkeypatch):
    import subprocess
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(subprocess, 'run', fake_run)
    RepoManager(str(tmp_path)).clone('pallets/click', ref='8.1.3')
    assert calls[0][:6] == ['git', 'clone', '--depth', '1', '--branch', '8.1.3']


def test_invalid_ref_is_rejected_before_clone(tmp_path, monkeypatch):
    import subprocess
    def forbidden(*args, **kwargs):
        pytest.fail('Invalid ref should not run git')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    with pytest.raises(ValueError):
        RepoManager(str(tmp_path)).clone('owner/repo', ref='--upload-pack=evil')


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['name'])
def test_recorded_benchmark_has_independent_holdout(case, tmp_path):
    result = run_case(case, str(tmp_path))
    assert result['status'] == 'fixed'
    assert result['regression_reproduced']
    assert result['holdout_passed']
    assert 'Authored' in (Path(result['artifacts']) / 'report.md').read_text()


def test_publish_reverification_failure_prevents_push(tmp_path, monkeypatch):
    artifacts = tmp_path / 'artifacts'
    artifacts.mkdir()
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    data = {'status': 'fixed', 'repo_slug': 'owner/repo', 'base_commit': 'abc',
            'issue': {'number': 1}, 'inspected_files': ['source.py'], 'backend': 'local',
            'attempts': [], 'explanation': ''}
    (artifacts / 'report.json').write_text(json.dumps(data))
    (artifacts / 'patch.diff').write_text('reviewed diff')
    (artifacts / 'test_patchpilot_regression.py').write_text('def test_bug():\n    assert True\n')
    calls = []
    def fake_run(cmd, cwd=None):
        calls.append(cmd)
        if cmd[:3] == ['git', 'rev-parse', 'HEAD']:
            return 'abc'
        if cmd[:3] == ['git', 'branch', '--show-current']:
            return 'main'
        return ''
    class FakeManager:
        def clone(self, slug):
            return str(checkout)
        def cleanup(self):
            pass
    from agent.patch_generator import PatchResult
    monkeypatch.setattr(publish_pr, 'RepoManager', FakeManager)
    monkeypatch.setattr(publish_pr, 'run', fake_run)
    monkeypatch.setattr(publish_pr, 'apply_patch', lambda *args: PatchResult(True))
    monkeypatch.setattr(publish_pr, 'run_tests', lambda *args, **kwargs: Result(failed=1))
    digest = publish_pr.approval_digest(artifacts)
    monkeypatch.setattr(sys, 'argv', ['publish_pr.py', str(artifacts), '--approve', digest])
    with pytest.raises(ValueError, match='Pre-publication'):
        publish_pr.main()
    assert not any(cmd[:2] == ['git', 'push'] or cmd[:3] == ['gh', 'pr', 'create'] for cmd in calls)


def test_test_runner_resolves_target_src_layout(tmp_path):
    from agent.test_runner import run_tests
    source = tmp_path / 'src' / 'unique_patchpilot_package'
    source.mkdir(parents=True)
    (source / '__init__.py').write_text('VALUE = 42\n')
    (tmp_path / 'test_import.py').write_text('from unique_patchpilot_package import VALUE\ndef test_value():\n    assert VALUE == 42\n')
    result = run_tests(str(tmp_path))
    assert result.all_passed, result.raw_output
