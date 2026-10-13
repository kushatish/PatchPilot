# Validation evidence

Evidence was collected locally on 13 October 2026. Run the commands yourself after changing the project.

| Check | Evidence | What it establishes |
| --- | --- | --- |
| Offline CSV demo | Original suite: 2 failures; regression: 2 failures; repaired full suite: 5 passes | Recorded fixture workflow works |
| Synthetic benchmark | Three recorded cases pass reproduction, repaired suites, and independent holdout tests | Workflow works across several small bug shapes |
| Historical Click issue #2395 | Two failing display tests at tag 8.1.3, resolved commit captured | A real historical issue was independently reproduced |
| Automated suite | 31 tests passed locally; rerun `python -m pytest` | Repair gates, retries, patch scope, imports, approvals, and failure paths |
| Docker demo | A dedicated GitHub Actions job is configured | Configuration exists; local Docker execution has not been verified |
| Real AI repairs | No API key configured in the validation environment | Unmeasured |
| Remote draft PR | GitHub CLI unavailable in the validation environment | Remote publishing is unverified; approval and failure gates are tested locally |

Commands:

```bash
python doctor.py
python -m pytest
python cli.py --demo
python benchmark.py
```

Do not present recorded replay success as an AI success rate. A project rating is subjective and cannot replace measured outcomes.
