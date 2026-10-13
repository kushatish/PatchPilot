#!/usr/bin/env python3
"""Report setup readiness without displaying credentials or changing configuration."""
import importlib.util
import json
import shutil
import sys
import config


def diagnose():
    checks = {
        'python_supported': sys.version_info >= (3, 10),
        'git_installed': bool(shutil.which('git')),
        'pytest_installed': importlib.util.find_spec('pytest') is not None,
        'anthropic_key_configured': bool(config.ANTHROPIC_API_KEY),
        'docker_installed': bool(shutil.which('docker')),
        'github_cli_installed': bool(shutil.which('gh')),
    }
    return {'checks': checks,
            'offline_demo_ready': all(checks[k] for k in ('python_supported', 'git_installed', 'pytest_installed')),
            'real_run_prerequisites_present': all(checks[k] for k in ('python_supported', 'git_installed', 'anthropic_key_configured', 'docker_installed')),
            'note': 'Presence checks only: Docker daemon/image readiness, GitHub authentication, model access and target dependencies still need verification.'}


if __name__ == '__main__':
    print(json.dumps(diagnose(), indent=2))
