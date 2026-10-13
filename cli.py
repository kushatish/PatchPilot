#!/usr/bin/env python3
"""PatchPilot CLI. Candidate generation does not publish changes."""
import argparse
import sys
import config
from agent.artifacts import write_artifacts
from agent.llm_client import get_llm_client
from agent.orchestrator import IssueResolverAgent


def main(argv=None):
    parser = argparse.ArgumentParser(description='PatchPilot: reproduce, repair, test, review')
    parser.add_argument('--repo', help='GitHub owner/repository or HTTPS URL')
    parser.add_argument('--issue', type=int)
    parser.add_argument('--ref', help='Branch or tag to reproduce a historical issue')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--no-llm', action='store_true', help='Demo-specific mock; not a general solver')
    parser.add_argument('--keep-workdir', action='store_true')
    parser.add_argument('--max-attempts', type=int, default=3, choices=range(1, 6))
    parser.add_argument('--execution', choices=['local', 'docker'], help='Real runs default to Docker; demo defaults to local')
    parser.add_argument('--docker-image', default='patchpilot-tests:local')
    parser.add_argument('--output', default=config.OUTPUT_DIR)
    parser.add_argument('--input-price', type=float, help='USD per million input tokens; supplied by you')
    parser.add_argument('--output-price', type=float, help='USD per million output tokens; supplied by you')
    args = parser.parse_args(argv)
    if not args.demo and (not args.repo or not args.issue or args.issue < 1):
        parser.error('Provide --repo and a positive --issue, or use --demo')
    if (args.input_price is None) != (args.output_price is None):
        parser.error('Supply both token prices or neither')
    if any(price is not None and price < 0 for price in (args.input_price, args.output_price)):
        parser.error('Token prices cannot be negative')
    agent = None
    try:
        llm = get_llm_client(force_mock=args.demo or args.no_llm)
        backend = args.execution or ('local' if args.demo else 'docker')
        print(f'[cli] Backend: {type(llm).__name__}; tests: {backend}')
        if backend == 'local' and not args.demo:
            print('[cli] Local mode executes repository code with your user permissions.')
        agent = IssueResolverAgent(llm, max_attempts=args.max_attempts, backend=backend, image=args.docker_image)
        report = agent.run(args.repo, args.issue, args.demo, ref=args.ref)
        if args.input_price is not None:
            report.estimated_cost_usd = round((report.input_tokens * args.input_price + report.output_tokens * args.output_price) / 1_000_000, 6)
        folder = write_artifacts(report, args.output)
        print(f'[cli] Status: {report.status}; artifacts: {folder.resolve()}')
        print(f'[cli] Open {folder.resolve() / "review.html"} to review the result')
        if args.keep_workdir:
            print(f'[cli] Working copy: {report.repo_path}')
        return 0 if report.status == 'fixed' else 1
    except Exception as exc:
        print(f'[cli] ERROR: {exc}', file=sys.stderr)
        return 1
    finally:
        if agent and not args.keep_workdir:
            agent.cleanup()


if __name__ == '__main__':
    sys.exit(main())
