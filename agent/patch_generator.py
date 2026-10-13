"""Validate patch scope and atomically apply an ordinary unified diff."""
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass


@dataclass
class PatchResult:
    applied: bool
    message: str = ''


def validate_patch(repo_path, diff_text, allowed_paths):
    root = Path(repo_path).resolve()
    headers = [line for line in diff_text.splitlines() if line.startswith(('--- ', '+++ '))]
    if not headers or len(headers) % 2:
        raise ValueError('Missing or unpaired unified diff headers')
    for index, line in enumerate(headers):
        prefix = '--- a/' if index % 2 == 0 else '+++ b/'
        if not line.startswith(prefix):
            raise ValueError('Only edits to existing files are allowed')
        rel = line[len(prefix):].split('\t', 1)[0]
        p = Path(rel)
        if p.is_absolute() or '..' in p.parts or rel not in allowed_paths:
            raise ValueError(f'Patch outside approved source context: {rel}')
        target = root / p
        if target.is_symlink() or root not in target.resolve().parents:
            raise ValueError('Symlinks and paths outside the working copy are forbidden')
        if index % 2 and rel != headers[index - 1][6:].split('\t', 1)[0]:
            raise ValueError('Renames are not allowed')
    if any(line.startswith(('GIT binary patch', 'new file mode', 'deleted file mode',
                            'old mode', 'new mode', 'rename from', 'rename to'))
           for line in diff_text.splitlines()):
        raise ValueError('Binary, mode, creation and deletion changes are forbidden')


def apply_patch(repo_path, diff_text, allowed_paths=None):
    if not isinstance(diff_text, str) or not diff_text.strip():
        return PatchResult(False, 'Empty diff')
    try:
        if allowed_paths is not None:
            validate_patch(repo_path, diff_text, allowed_paths)
        with tempfile.TemporaryDirectory() as directory:
            patch = Path(directory) / 'candidate.diff'
            patch.write_text(diff_text.rstrip('\n') + '\n')
            cmd = ['git', 'apply', '--whitespace=nowarn', '-p1']
            checked = subprocess.run(cmd + ['--check', str(patch)], cwd=repo_path,
                                     capture_output=True, text=True, timeout=30)
            if checked.returncode:
                return PatchResult(False, checked.stderr.strip())
            result = subprocess.run(cmd + [str(patch)], cwd=repo_path,
                                    capture_output=True, text=True, timeout=30)
            return PatchResult(result.returncode == 0, result.stderr.strip() or 'Patch applied cleanly')
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        return PatchResult(False, str(exc))
