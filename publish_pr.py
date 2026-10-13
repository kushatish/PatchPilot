#!/usr/bin/env python3
"""Explicitly approved publishing of a reviewed candidate using GitHub CLI."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from agent.github_client import GitHubClient
from agent.repo_manager import RepoManager
from agent.patch_generator import apply_patch
from agent.test_runner import run_tests


def approval_digest(folder):
    digest = hashlib.sha256()
    for name in ('report.json', 'patch.diff', 'test_patchpilot_regression.py'):
        digest.update(name.encode())
        digest.update((folder / name).read_bytes())
    return digest.hexdigest()


def run(cmd, cwd=None):
    return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def main():
    parser = argparse.ArgumentParser(description='Review first, then explicitly approve a draft PR')
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('--approve', help='SHA-256 digest displayed by the preview command')
    args = parser.parse_args()
    folder = args.artifacts.resolve()
    data = json.loads((folder / 'report.json').read_text())
    if data['status'] != 'fixed' or not data.get('repo_slug'):
        parser.error('Only a successful real-repository run can be published')
    digest = approval_digest(folder)
    slug = GitHubClient.parse_repo_slug(data['repo_slug'])
    if not args.approve:
        print(f'Target: {slug}; issue: {data["issue"]["number"]}; base: {data["base_commit"]}')
        print(f'Review: {folder / "review.html"}')
        print(f'Approval digest: {digest}')
        print('After reviewing, run this command again with --approve DIGEST. This pushes a branch and opens a draft PR.')
        return 0
    if args.approve != digest:
        parser.error('Approval digest does not match the current artifacts')
    run(['gh', 'auth', 'status'])
    manager = RepoManager()
    pushed = False
    try:
        root = Path(manager.clone(slug))
        if run(['git', 'rev-parse', 'HEAD'], root) != data['base_commit']:
            raise ValueError('Default branch changed since testing; generate and review a new candidate')
        base = run(['git', 'branch', '--show-current'], root)
        branch = 'codex/patchpilot-' + str(data['issue']['number']) + '-' + digest[:10]
        run(['git', 'checkout', '-b', branch], root)
        allowed = {p for p in data['inspected_files'] if Path(p).suffix == '.py'
                   and not Path(p).name.startswith('test_') and not Path(p).name.endswith('_test.py')
                   and Path(p).name != 'conftest.py' and 'tests' not in Path(p).parts}
        applied = apply_patch(str(root), (folder / 'patch.diff').read_text(), allowed)
        if not applied.applied:
            raise ValueError(applied.message)
        regression = root / 'test_patchpilot_regression.py'
        if regression.exists():
            raise ValueError('Regression filename already exists')
        regression.write_bytes((folder / 'test_patchpilot_regression.py').read_bytes())
        # Recheck the exact reviewed candidate immediately before committing or pushing.
        for paths in ([regression.name], None):
            result = run_tests(str(root), paths, backend=data.get('backend', 'docker'),
                               image=data.get('docker_image', 'patchpilot-tests:local'))
            if not result.all_passed:
                raise ValueError('Pre-publication verification failed: ' + result.summary + '\n' + result.raw_output)
        run(['git', 'add', '--', *sorted(allowed), regression.name], root)
        run(['git', 'commit', '-m', f'Fix issue #{data["issue"]["number"]} with regression coverage'], root)
        body = folder / 'pr-body.md'
        body.write_text(f'Addresses #{data["issue"]["number"]}.\n\n' + data.get('explanation', '')
                        + '\n\nGenerated regression failed before the fix and passed afterward. '
                        + 'The full pytest suite passed in the recorded environment. Human review is required.\n'
                        + f'\nExecution backend: {data["backend"]}; attempts: {len(data["attempts"])}.\n')
        run(['git', 'push', '-u', 'origin', branch], root)
        pushed = True
        url = run(['gh', 'pr', 'create', '--repo', slug, '--draft', '--base', base, '--head', branch,
                   '--title', f'Fix issue #{data["issue"]["number"]}', '--body-file', str(body)], root)
        (folder / 'pull-request.txt').write_text(url + '\n')
        print(url)
        return 0
    finally:
        if pushed:
            print('The remote branch was pushed; it remains on GitHub even if PR creation failed.')
        manager.cleanup()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'Publish failed: {exc}')
        raise SystemExit(1)
