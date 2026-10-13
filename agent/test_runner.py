"""Pytest execution with structured results and optional Docker isolation."""
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
import config


@dataclass
class TestResult:
    passed: int = 0
    failed: int = 0
    errors: int = 0
    returncode: int = 1
    raw_output: str = ""
    timed_out: bool = False

    @property
    def all_passed(self):
        return self.returncode == 0 and self.passed > 0 and not self.failed and not self.errors

    @property
    def reproduced(self):
        return self.returncode == 1 and self.failed > 0 and not self.errors and not self.timed_out

    @property
    def summary(self):
        if self.timed_out:
            return 'TIMED OUT'
        return f'{self.passed} passed, {self.failed} failed, {self.errors} errors (exit {self.returncode})'


def _parse_summary(output):
    tail = '\n'.join(output.strip().splitlines()[-8:])
    return tuple(int(m.group(1)) if (m := re.search(r'(\d+) ' + kind, tail)) else 0
                 for kind in ('passed', 'failed', 'error'))


def build_command(repo_path, test_paths=None, backend='local', image='patchpilot-tests:local', name=None):
    pytest = ['-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider']
    pytest += list(test_paths or [])
    if backend == 'local':
        return [sys.executable] + pytest
    if backend != 'docker':
        raise ValueError('Unknown test backend')
    return ['docker', 'run', '--rm', '--pull=never', '--name', name or 'patchpilot-' + uuid.uuid4().hex,
            '--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--pids-limit=128', '--memory=512m', '--cpus=1', '--user=65534:65534',
            '--tmpfs=/tmp:rw,nosuid,size=128m',
            '--mount', f'type=bind,src={Path(repo_path).resolve()},dst=/repo,readonly',
            '--workdir=/repo', '--env=PYTHONDONTWRITEBYTECODE=1', '--env=HOME=/tmp',
            '--env=PYTHONPATH=/repo/src:/repo', '--entrypoint=python', image] + pytest


def run_tests(repo_path, test_paths=None, backend='local', image='patchpilot-tests:local'):
    name = 'patchpilot-' + uuid.uuid4().hex
    cmd = build_command(repo_path, test_paths, backend, image, name)
    # Local execution is explicitly opt-in. Do not pass known API credentials.
    env = {k: v for k, v in os.environ.items()
           if not any(word in k.upper() for word in ('TOKEN', 'SECRET', 'API_KEY', 'PASSWORD'))}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    root = Path(repo_path).resolve()
    env['PYTHONPATH'] = os.pathsep.join([str(root / 'src'), str(root)])
    try:
        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True,
                                timeout=config.TEST_TIMEOUT_SECONDS, env=env)
    except subprocess.TimeoutExpired as exc:
        def decode(value):
            return value.decode(errors='replace') if isinstance(value, bytes) else value or ''
        return TestResult(raw_output=decode(exc.stdout) + decode(exc.stderr), timed_out=True)
    except OSError as exc:
        return TestResult(raw_output=str(exc), returncode=127)
    finally:
        if backend == 'docker':
            try:
                subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                pass
    output = result.stdout + '\n' + result.stderr
    passed, failed, errors = _parse_summary(output)
    return TestResult(passed, failed, errors, result.returncode, output)
