# Changes

## Version 2 prototype

Added generated regression tests before repair, independent bounded retries, full-suite verification, AST/filename ranking, local import context, patch scope validation, restricted Docker execution, unique review artifacts, explicit digest-based draft PR publication, evaluation metrics, automated tests, and GitHub Actions.

Real runs now require an Anthropic key rather than silently using the demo mock. Unsuccessful runs now exit nonzero. Test execution uses the CLI interpreter in local mode. Timeout output handles bytes safely. Removed unused Gemini configuration.

The original CSV demo bug remains intentional. Docker runtime and remote GitHub publication require validation on a configured machine. Real-world issue success rates are not claimed.

## Version 2.1 evidence and publishing improvements

Added explicit branch/tag selection, definition-focused source excerpts for large files, src-layout import support, a setup doctor, a three-case recorded benchmark with independent holdout tests, and a captured reproduction of historical Click issue #2395. Publishing now reruns regression and full-suite verification before push. Added a Docker demonstration CI job and interview/evidence documentation. Live AI repair and remote publishing results remain unmeasured.
