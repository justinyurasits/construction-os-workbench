"""Live evaluation of LLM drafting against the package's acceptance cases. Calls the real Claude API.

Never run in CI and not a test (pytest only collects tests/). Run it yourself:

    python scripts/live_eval.py --corpus ../construction-os-corpus [--model claude-sonnet-5-5] [--effort high]
                                [--cases 1,4] [--keep DIR] [--runs N] [--record]

Each draft case's request.md is drafted through the same pipeline as the CLI, in a throwaway project store
(or --keep DIR), and its priced totals and flags are compared with expected.yaml. A case with
pricing_structure (estimating from cost history) is graded on structure, not a total: every required scope item
has a line, every line has a source, the arithmetic is exact, estimates are on the PM checklist, and general
conditions follow the threshold rule. Schedule impact and general conditions are checked where expected.yaml
states them. The checks are construction_os.acceptance, the same code the offline tests grade recordings with.

--runs N drafts each case N times, to show run-to-run variance. --record saves the accepted proposal of a case
whose checks all pass as the case's recorded_proposal.json in the package (the last passing run, with --runs);
review the draft before committing it, since the offline tests replay it on every pull request. Advice cases are skipped until step 7. Contract terms aren't applied until step 6, so a case whose expected pricing comes from a
contract is graded against its company-standard total and must raise contract_terms_not_applied.
"""
import argparse
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

from construction_os.acceptance import cases, expected as read_expected, grade, money, write_recording
from construction_os.drafting import DraftingError
from construction_os.drafting.cli import draft_request, real_client
from construction_os.drafting.config import Settings
from construction_os.projects import FileProjectStore
from construction_os.rendering import load_package


def usage(attempts):
    totals = Counter()
    for attempt in attempts:
        for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            totals[key] += (attempt.get("usage") or {}).get(key) or 0
    return totals


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--model", help="Claude model ID (default: DRAFT_MODEL or the built-in default)")
    parser.add_argument("--effort", help="effort level (default: DRAFT_EFFORT or high)")
    parser.add_argument("--cases", help="comma-separated case ids to run, e.g. 1,4 (default: all)")
    parser.add_argument("--keep", help="project store root to keep the drafts in (default: a temporary folder)")
    parser.add_argument("--runs", type=int, default=1, help="drafts per case (default: 1)")
    parser.add_argument("--record", action="store_true",
                        help="save a fully passing run's proposal as the case's recorded_proposal.json")
    args = parser.parse_args(argv)

    corpus = Path(args.corpus)
    package = load_package(corpus)
    root = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="pco-live-eval-"))
    store = FileProjectStore(root, forbidden=[package.root])
    client = real_client(Settings(model=args.model or "", effort=args.effort or ""))
    wanted = {int(c) for c in args.cases.split(",")} if args.cases else None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    print(f"Model {client.settings.model}, effort {client.settings.effort}; drafts in {root}\n")
    failures = 0
    for case in cases(corpus):
        expected = read_expected(case)
        if wanted and expected["id"] not in wanted:
            continue
        print(f"== Case {expected['id']}: {expected['title']}")
        if expected["mode"] == "advice":
            print("   skipped: advice (step 7)\n")
            continue
        passing_runs = 0
        for run in range(1, args.runs + 1):
            if args.runs > 1:
                print(f"   -- run {run} of {args.runs}")
            started = time.monotonic()
            try:
                result = draft_request(package, store, f"eval-{case.name}-{stamp}-{run}", None,  # name unknown: [Project name]
                                       case / "request.md", [], client)
            except DraftingError as error:
                failures += 1
                print(f"   FAILED to draft after {time.monotonic() - started:.1f}s:\n   {error}\n")
                continue
            elapsed = time.monotonic() - started
            structure = "pricing_structure" in expected["exact"]
            checks, kinds = grade(expected, result, package)
            for name, want, got, passed in checks:
                print(f"   {'PASS' if passed else 'FAIL'}  {name}: expected {want}; got {got}")
            failed = sum(1 for *_, passed in checks if not passed)
            failures += failed
            tokens = usage(result.attempts)
            served = sorted({a["model"] for a in result.attempts})
            print(f"   flags: {dict(kinds)}")
            print(f"   attempts {len(result.attempts)}, served by {', '.join(served)}, {elapsed:.1f}s; tokens in "
                  f"{tokens['input_tokens']}, out {tokens['output_tokens']}, cache read "
                  f"{tokens['cache_read_input_tokens']}, cache write {tokens['cache_creation_input_tokens']}")
            print(f"   {result.docx_path}")
            print(f"   {result.checklist_path}" + ("  (total not graded: " + money(result.priced.total) + ")"
                                                 if structure else ""))
            if not failed:
                passing_runs += 1
                if args.record:
                    print(f"   recorded: {write_recording(case, result)}")
            print()
        if args.runs > 1:
            print(f"   {passing_runs} of {args.runs} runs passed every check\n")
    print("All checks passed." if not failures else f"{failures} check(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
