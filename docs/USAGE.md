# PatchPilot

**An AI-assisted Python bug-fixing workflow that reproduces a problem, proposes a repair, and prepares evidence for review.**

Give PatchPilot a GitHub repository and issue number. It reads the issue, finds relevant code, creates a regression test, checks that the test fails, and asks Claude for a candidate fix. A candidate is accepted only when the regression test and the full pytest suite pass. You review the patch before publishing anything.

This is a working prototype, not a guarantee of correct fixes. The included offline demo uses a deterministic mock. Real AI performance must be measured on real issues; no real-world success rate is claimed here.

## Quick start

Use Python 3.10+ and Git. From this project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python cli.py --demo
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`. Test subprocesses use the same interpreter as the CLI.

The demo requires no API key or network after dependencies are installed. It copies the intentionally broken CSV parser into a temporary Git repository. Expected evidence:

| Check | Expected result |
| --- | --- |
| Original suite | 1 passed, 2 failed |
| Newly generated regression tests | 2 failed before the fix |
| Regression tests after repair | 2 passed |
| Full suite after repair | 5 passed |
| Status | `fixed` |

The fixture remains broken so you can repeat the demo. Its predefined test and fix exercise the workflow, rather than demonstrate AI reasoning on an unfamiliar problem.

## Features implemented

- **Regression before repair:** generates a pytest test from the issue and source context; refuses to repair if it does not fail cleanly.
- **Bounded retries:** up to 1–5 candidates, with failed diffs and test output fed back to the model. Each attempt starts from the original source.
- **Full-suite verification:** runs the regression explicitly and then the entire discovered pytest suite after each applied candidate.
- **Stronger search:** combines keyword counts, filename matches, AST function/class names, and one-hop local import expansion.
- **Restricted patch scope:** only inspected existing Python source files may change. Test edits, symlink targets, renames, binary patches, and mode changes are rejected.
- **Docker execution:** real runs default to a container with networking disabled, a read-only repository mount, a non-root user, dropped capabilities, and resource limits.
- **Review artifacts:** unique run folders contain a diff, generated regression, JSON/Markdown reports, and a portable HTML review page.
- **Explicit draft PR publishing:** a separate command previews the destination and requires a digest of the reviewed artifacts before pushing a branch.
- **Evaluation:** a manifest runner records candidate success rate, elapsed time, attempts, and model token usage.
- **Automated checks:** tests cover the repair workflow, failed attempts, patch boundaries, search, timeouts, and approval digests. GitHub Actions runs tests and the demo.

## Real GitHub runs

```bash
cp .env.example .env
```

Set `ANTHROPIC_API_KEY` in `.env`. `ANTHROPIC_MODEL` defaults to `claude-sonnet-4-5`; choose a model available to your account. `GITHUB_TOKEN` is optional and authenticates issue API requests only. Git cloning and publishing use your separately configured Git credentials.

Real runs require a key and do not silently fall back to a mock. Source context, issue text, and test output are sent to Anthropic. API usage may incur charges.

### Prepare the Docker test image

Install and start Docker, then build the supplied image:

```bash
docker build -t patchpilot-tests:local -f docker/Dockerfile .
python cli.py --repo owner/repository --issue 27
```

The image includes Python 3.12 and pytest. Target-specific dependencies must be installed into a **custom image**, before execution. Example:

```dockerfile
FROM patchpilot-tests:local
USER root
COPY target-requirements.txt /tmp/target-requirements.txt
RUN pip install --no-cache-dir -r /tmp/target-requirements.txt
USER 65534:65534
```

Build that image and select it with `--docker-image your-image:tag`. Review dependencies before installing them. Image builds need network access; test execution uses `--network=none` and `--pull=never`.

Containers use a read-only repository mount and a writable temporary `/tmp`. Tests requiring writes inside the repository, network services, or special system libraries may need adaptation. PatchPilot does not automatically install target dependencies or change container privileges. Container restrictions follow the [Docker run documentation](https://docs.docker.com/reference/cli/docker/container/run/). Containers reduce exposure but are not a complete security boundary for hostile code; use a disposable machine or VM for that case.

### Local execution for trusted projects

```bash
python cli.py --repo owner/repository --issue 27 --execution local
```

Install the target dependencies into the CLI environment first. Local mode runs repository code with your user permissions; known credential environment variables are removed from test subprocesses, but filesystem access and other environment values remain available. Demo mode defaults to local execution because it uses the bundled trusted fixture.

## CLI options

| Option | Meaning |
| --- | --- |
| `--demo` | Run the offline fixture with the mock backend. |
| `--repo`, `--issue` | GitHub slug/HTTPS URL and positive issue number. |
| `--ref TAG_OR_BRANCH` | Checkout a specific branch or tag for repeatable historical evaluations. |
| `--max-attempts 3` | Candidate limit, between 1 and 5; default 3. |
| `--execution docker` | Test execution backend; real default is Docker, demo default is local. |
| `--docker-image IMAGE` | Prebuilt test image; default `patchpilot-tests:local`. |
| `--keep-workdir` | Retain the isolated repository copy for inspection. |
| `--output PATH` | Artifact root; default `output/` in the project folder. |
| `--input-price`, `--output-price` | Optional USD prices per million tokens for an estimated API cost; provide both. |
| `--no-llm` | Force the fixture-specific mock. It is not a general issue solver. |

Use `python cli.py --help` for usage. Operational constants such as file limits and the test timeout live in `config.py`. Credentials and model selection load from `.env`; existing environment variables take precedence.

## Review the result

Each run creates its own folder:

```text
output/<UTC timestamp>-<unique ID>/
├── report.json                    # Structured state, attempts, logs, metrics
├── report.md                      # Evidence and full captured test output
├── review.html                    # Escaped, browser-readable report and diff
├── patch.diff                     # Successful source candidate, if any
└── test_patchpilot_regression.py   # Generated test, if any
```

Open the printed `review.html` path in a browser. Check the generated test against the issue, check the source changes, and inspect baseline and post-patch output. The page is a static review artifact; approval and publishing happen through the separate CLI below.

| Status | Meaning |
| --- | --- |
| `fixed` | A generated regression failed before repair, then it and the full suite passed. Candidate is ready for review. |
| `no_repro` | No relevant source was found, or the generated test did not reproduce a clean test failure. |
| `test_error` | The baseline environment, collection, or execution failed. |
| `patch_failed` | Candidate attempts were exhausted; editable source was restored. |
| `error` | An exception prevented completion; details are recorded. |

The CLI exits 0 only for `fixed`, 1 for unsuccessful runs/errors, and 2 for invalid arguments. A successful status proves behavior under the generated tests, not that the tests accurately capture every requirement. Full suite means pytest's discovery under the target project's existing configuration, which may exclude some tests.

## Open a draft pull request after review

Install GitHub CLI (`gh`) and authenticate it, and configure Git push access to the target repository. Publishing directly requires write permission; automatic fork creation is not implemented.

Preview a successful real run:

```bash
python publish_pr.py output/RUN_ID
```

Review the HTML report and copy the displayed approval digest. Then explicitly authorize publication:

```bash
python publish_pr.py output/RUN_ID --approve DISPLAYED_DIGEST
```

This command verifies the artifact digest, clones the repository again, checks that the default branch still matches the tested base commit, applies the reviewed patch and regression, commits to `codex/patchpilot-...`, pushes the branch, and opens a **draft** PR. It does not merge anything. If the base branch moved, regenerate and review the candidate. If push succeeds but PR creation fails, the remote branch remains; the command reports this. Do not edit artifact JSON manually to bypass verification.

## Evaluate performance

Start with the workflow smoke evaluation:

```bash
python evaluate.py --demo
```

This measures only the predefined fixture, not general AI success. For real evaluation, create `cases.json` containing actual issues you have selected:

```json
[
  {"repo": "owner/repository", "issue": 27}
]
```

The example is a placeholder, not a verified benchmark. Use reproducible issues and appropriate test images:

```bash
python evaluate.py cases.json --docker-image your-tests:tag
```

The runner writes `evaluation.json` beside the last case's artifacts. It records case status, elapsed seconds, attempts, token counts, and the fraction reaching `fixed`. Evaluation exits nonzero when any case fails. Manually assess whether successful candidates really resolve their issues. Use `--input-price` and `--output-price` on either CLI for cost estimates; prices are supplied by you rather than hardcoded. There are no measured real-world results shipped with this project.

## Development and project structure

```bash
python -m pytest
python cli.py --demo
```

`pytest.ini` limits this project's own test discovery to `tests/`, leaving the intentionally failing demo fixture out of the project test suite. The agent executes the copied fixture independently.

```text
cli.py                     CLI and exit codes
evaluate.py                Issue manifest evaluation
publish_pr.py              Approved draft PR publishing
benchmark.py               Synthetic repair and holdout evaluation
doctor.py                  Prerequisite checks
benchmarks/                Historical issue reproducer and manifest
docs/                      Evidence, case study, interview guide
config.py                  API settings and operational constants
agent/
  github_client.py         Issue ingestion and slug validation
  repo_manager.py          Temporary Git clones/copies and cleanup
  code_search.py           Keyword/AST ranking and import context
  llm_client.py            Claude API, usage counts, regression and patch generation
  orchestrator.py          Reproduction gate, retries, full-suite checks
  patch_generator.py       Patch validation and application
  test_runner.py           Local/Docker pytest execution
  artifacts.py             Unique JSON/Markdown/HTML reports
demo_repo/                 Original intentional CSV bug and tests
docker/Dockerfile          Base test image
tests/                     PatchPilot behavior and boundary tests
.github/workflows/tests.yml Automated tests and offline demo
```

## Limitations and next work

- Python/pytest only; existing files only; no multi-language repair or dependency updates.
- Shallow clone of the default branch or an explicitly selected branch/tag via `--ref`. Historical candidates cannot be published against a changed default branch.
- Generated tests can be wrong. Clean test failure is necessary evidence, not proof of semantic correctness.
- Context is bounded, import expansion is one hop, and search is not a complete call graph or semantic index.
- Retry attempts can incur additional API cost. Token-based cost estimates omit caching or other billing adjustments.
- Real GitHub performance, container execution, and remote publishing require their respective credentials/runtime and should be validated in your environment.
- No automatic forks, merges, interactive web approval, or automatic installation of untrusted dependencies.

## Version 2.1: stronger evidence

Run `python doctor.py` to check basic prerequisites without revealing credentials. Run `python benchmark.py` for three **recorded, synthetic** repair cases (empty averages, whitespace normalization, inclusive bounds). The benchmark adds independent holdout tests only after generation, so the backend cannot see them. This validates workflow mechanics; its success rate is not an AI-performance claim.

With a configured API key and test image, `python benchmark.py --ai` uses actual Claude on the same synthetic problems. `--execution local` is available for these trusted fixtures. Real runs now support `--ref` in both the CLI and evaluation manifest. Context extraction preserves matching function/class definitions in large files instead of always showing the file prefix. Both test backends add the target `src/` directory to the Python import path.

A real historical bug in Click was independently reproduced on version 8.1.3: both UTF-8 display tests fail with `UnicodeEncodeError`. See [the case study](CASE_STUDY.md) and the captured baseline in `click-baseline.json`. No AI repair of that case was attempted because an API key is not configured here.

Publishing now reruns the regression and full suite immediately before committing/pushing. GitHub Actions also includes a Docker demo job; it must actually run on GitHub before claiming container verification. Read [validation evidence](VALIDATION.md) and [interview preparation](INTERVIEW.md) for accurate claims and a short demonstration plan.

The next milestone is real AI evaluation with human-reviewed outcomes. That evidence matters more than calling the project production-ready.
