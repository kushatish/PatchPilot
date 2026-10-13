# Explain and demonstrate PatchPilot

## Thirty-second explanation

“PatchPilot is a Python tool that uses AI to propose bug fixes from GitHub issues. It first generates a test to reproduce the issue, then tries a patch and runs both the regression and the full test suite. It can retry using failure feedback. It prepares a report for review and can open a draft pull request after explicit approval.”

## Three-minute demo

1. Show `demo_repo/ISSUE.md` and explain the empty-date crash.
2. Run `python cli.py --demo` and point out the failing-before/passing-after evidence.
3. Open the generated `review.html`, explaining the diff and test results.
4. Run `python benchmark.py` and explain independent holdout tests.
5. Show the historical Click case study and clearly distinguish manual reproduction from AI repair.

The demo and default benchmark use authored responses, not live AI. Explain this before showing their results.

## Questions to prepare for

- Why add a regression test before the fix? It establishes a failure the repair must address.
- Why run independent holdout tests? A proposed fix may satisfy one generated test while missing related behavior.
- Why reset source between retries? New patches must target a known baseline rather than accumulate accidental changes.
- Why prevent test edits? A candidate should fix the behavior rather than weaken verification.
- Why use Docker? It limits filesystem access, networking and resource use; it is not a complete hostile-code defense.
- Why pin a version? A historical bug may already be fixed on the latest default branch.
- What does passing tests prove? Only behavior covered by those tests in that environment; human review remains necessary.
- What is still unverified? General AI success, local Docker execution and actual remote PR publication.

Describe your own contribution accurately. Understand the implementation and acknowledge AI assistance where it was used.
