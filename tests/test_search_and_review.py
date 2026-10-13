import json
from pathlib import Path
import pytest
from agent.code_search import search_repository, expand_import_context
from publish_pr import approval_digest


def test_symbol_ranking_and_import_expansion(tmp_path):
    (tmp_path / 'service.py').write_text('from helper import normalize\ndef parse_upload():\n    return normalize()\n')
    (tmp_path / 'helper.py').write_text('def normalize():\n    return 1\n')
    (tmp_path / 'comments.py').write_text('# parse_upload\n')
    matches = search_repository(str(tmp_path), ['parse_upload'])
    assert matches[0].path == 'service.py'
    context = expand_import_context(str(tmp_path), {'service.py': (tmp_path / 'service.py').read_text()})
    assert 'helper.py' in context


def test_approval_digest_changes_when_patch_changes(tmp_path):
    for name in ('report.json', 'patch.diff', 'test_patchpilot_regression.py'):
        (tmp_path / name).write_text('original')
    first = approval_digest(tmp_path)
    (tmp_path / 'patch.diff').write_text('modified')
    assert approval_digest(tmp_path) != first


def test_review_escapes_html(tmp_path):
    from agent.artifacts import write_artifacts
    from agent.orchestrator import RunReport
    from agent.github_client import Issue
    folder = write_artifacts(RunReport(issue=Issue(1, '<script>alert(1)</script>', 'body')), tmp_path)
    page = (folder / 'review.html').read_text()
    assert '<script>' not in page
    assert '&lt;script&gt;' in page


def test_publish_preview_never_calls_git_or_github(monkeypatch, tmp_path, capsys):
    import sys
    import publish_pr
    (tmp_path / 'report.json').write_text(json.dumps({'status': 'fixed', 'repo_slug': 'owner/repo',
                                                    'issue': {'number': 1}, 'base_commit': 'abc'}))
    for name in ('patch.diff', 'test_patchpilot_regression.py'):
        (tmp_path / name).write_text('reviewed data')
    def forbidden(*args, **kwargs):
        pytest.fail('Preview must not execute external commands')
    monkeypatch.setattr(publish_pr, 'run', forbidden)
    monkeypatch.setattr(sys, 'argv', ['publish_pr.py', str(tmp_path)])
    assert publish_pr.main() == 0
    assert 'Approval digest' in capsys.readouterr().out


def test_publish_invalid_approval_stops_before_network(monkeypatch, tmp_path):
    import sys
    import publish_pr
    (tmp_path / 'report.json').write_text(json.dumps({'status': 'fixed', 'repo_slug': 'owner/repo'}))
    for name in ('patch.diff', 'test_patchpilot_regression.py'):
        (tmp_path / name).write_text('data')
    def forbidden(*args, **kwargs):
        pytest.fail('Unapproved publication must not execute external commands')
    monkeypatch.setattr(publish_pr, 'run', forbidden)
    monkeypatch.setattr(sys, 'argv', ['publish_pr.py', str(tmp_path), '--approve', 'wrong'])
    with pytest.raises(SystemExit) as exc:
        publish_pr.main()
    assert exc.value.code == 2
