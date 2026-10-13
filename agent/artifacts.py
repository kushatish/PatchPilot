"""Unique, portable run artifacts and a browser-readable review page."""
import html
import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path


def write_artifacts(report, output_root):
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    folder = Path(output_root) / run_id
    folder.mkdir(parents=True)
    data = asdict(report)
    (folder / 'report.json').write_text(json.dumps(data, indent=2, default=lambda obj: sorted(obj) if isinstance(obj, set) else str(obj)))
    issue = report.issue.title if report.issue else 'Issue unavailable'
    lines = [f'# PatchPilot: {issue}', f'\nStatus: **{report.status}**',
             f'\nExecution: {report.backend}; elapsed: {report.elapsed_seconds}s',
             f'\nTokens: {report.input_tokens} input, {report.output_tokens} output',
             f'\nEstimated API cost: {report.estimated_cost_usd if report.estimated_cost_usd is not None else "not configured"}',
             '\n## Evidence']
    for name in ('baseline_tests', 'regression_before', 'regression_after', 'post_patch_tests'):
        result = getattr(report, name)
        lines.append(f'\n### {name}\n')
        lines.append(result.summary + '\n\n```text\n' + result.raw_output + '\n```' if result else 'Not run')
    lines += ['\n## Explanation\n', report.explanation or report.patch_reasoning,
              '\n## Candidate diff\n', '```diff\n' + report.diff + '\n```',
              '\n## Generated regression\n', '```python\n' + report.regression_code + '\n```',
              '\n## Attempts\n']
    for attempt in report.attempts:
        lines.append('```json\n' + json.dumps(attempt, indent=2) + '\n```')
    lines += ['\n## Trace\n'] + ['- ' + entry for entry in report.log]
    markdown = '\n'.join(lines)
    (folder / 'report.md').write_text(markdown)
    if report.diff:
        (folder / 'patch.diff').write_text(report.diff)
    if report.regression_code:
        (folder / 'test_patchpilot_regression.py').write_text(report.regression_code)
    page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<title>PatchPilot review</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{max-width:1050px;margin:40px auto;padding:0 24px;background:#101827;color:#e5e7eb;font:16px system-ui}a{color:#93c5fd}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#1f2937;padding:20px;border-radius:10px}h1{color:#a7f3d0}</style>
<h1>PatchPilot review</h1><p>Review the diff and regression test against the original issue. Passing tests do not establish semantic correctness.</p>
<p><a href="report.json">Structured report</a> · <a href="report.md">Markdown report</a></p><pre>'''
    (folder / 'review.html').write_text(page + html.escape(markdown) + '</pre></html>')
    return folder
