#!/usr/bin/env python3
"""
Eval-pack CI gate (trust stack Phase 3d).

OFFLINE MODE (default — no keys, no network, CI-safe):
    For each of the 30 scenarios this verifies BOTH directions:
      (a) every targeted grader + the auto structure/provenance suite PASSES
          the scenario's known-good fixture report, and
      (b) at least one targeted grader CATCHES the scenario's buggy fixture
          (the documented failure mode is actually detectable).
    A scenario passes only if (a) and (b) both hold.

LIVE MODE (--live):
    ⚠ NEEDS LIVE VERIFICATION — generates a real report per scenario through
    DraftGenerator (three Anthropic calls each) and grades THAT output.
    Requires ANTHROPIC_API_KEY; if it is missing the script DEGRADES to
    offline mode with a loud warning rather than crashing. Live mode has
    never been run against a live model from this machine.

Exit code: 0 if pass_rate >= threshold (default 0.90), else 1 — wire this
into CI as a merge gate.

Usage:
    python scripts/run_eval_pack.py [--live] [--threshold 0.9] [--verbose] [--save out.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # needed here, not just in draft_generator.py — main() checks
                # ANTHROPIC_API_KEY before draft_generator is ever imported

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from eval_pack.graders import grade_report          # noqa: E402
from eval_pack.scenarios import SCENARIOS           # noqa: E402


def run_offline(verbose: bool) -> list[dict]:
    """Grade the good/buggy fixtures — proves the graders catch each bug."""
    results = []
    for sc in SCENARIOS:
        good_results = grade_report(sc["good_report"], sc["expected"])
        good_failures = [r for r in good_results if not r["passed"]]

        buggy_results = grade_report(sc["buggy_report"], sc["expected"])
        buggy_caught = [r for r in buggy_results if r["targeted"] and not r["passed"]]

        passed = not good_failures and bool(buggy_caught)
        results.append({
            "id": sc["id"], "title": sc["title"], "category": sc["category"],
            "source": sc["source"], "mode": "offline", "passed": passed,
            "good_failures": [f"{r['grader']}: {r['detail']}" for r in good_failures],
            "bug_caught_by": [r["grader"] for r in buggy_caught],
        })
        if verbose or not passed:
            icon = "✅" if passed else "❌"
            print(f"  {icon} {sc['id']:16} {sc['title'][:70]}")
            for r in good_failures:
                print(f"        ↳ good fixture failed {r['grader']}: {r['detail']}")
            if not buggy_caught:
                print("        ↳ buggy fixture NOT caught by any targeted grader")
    return results


def run_live(verbose: bool) -> list[dict]:
    """
    ⚠ NEEDS LIVE VERIFICATION — never executed against a live model from this
    machine. Generates a real draft per scenario and grades it.
    """
    import asyncio
    import uuid
    from datetime import datetime

    from draft_generator import DraftGenerator
    from models import PatientUpdate

    generator = DraftGenerator()
    results = []

    for sc in SCENARIOS:
        try:
            updates = []
            base = datetime(2026, 7, 1)
            for raw in sc["input_updates"]:
                h, m = map(int, raw["time"].split(":"))
                updates.append(PatientUpdate(
                    id=str(uuid.uuid4()), shift_id=f"EVAL-{sc['id']}",
                    patient_id=sc["emr_state"]["patient_id"], nurse_id="EVAL-NURSE",
                    timestamp=base.replace(hour=h, minute=m),
                    update_type=raw["type"], transcription=raw["text"],
                ))
            organized = generator._organize_updates(updates)
            report = asyncio.run(generator._generate_handoff_summary_async(
                sc["emr_state"], organized, len(updates)))
            graded = grade_report(report, sc["expected"])
            failures = [r for r in graded if not r["passed"]]
            passed = not failures
        except Exception as exc:
            passed, failures = False, [{"grader": "generation", "detail": str(exc)}]

        results.append({
            "id": sc["id"], "title": sc["title"], "category": sc["category"],
            "source": sc["source"], "mode": "live", "passed": passed,
            "failures": [f"{r['grader']}: {r['detail']}" for r in failures],
        })
        icon = "✅" if passed else "❌"
        print(f"  {icon} {sc['id']:16} {sc['title'][:70]}")
        if verbose:
            for r in failures:
                print(f"        ↳ {r['grader'] if isinstance(r, dict) else r}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Cascade AI eval-pack CI gate")
    parser.add_argument("--live", action="store_true",
                        help="generate real reports via the LLM (NEEDS LIVE VERIFICATION)")
    parser.add_argument("--threshold", type=float, default=0.90,
                        help="minimum pass rate to exit 0 (default 0.90)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--save", metavar="PATH", help="write full results JSON here")
    args = parser.parse_args()

    mode = "live" if args.live else "offline"
    if args.live and not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠ NEEDS LIVE VERIFICATION: --live requested but ANTHROPIC_API_KEY is not set.")
        print("  Degrading to OFFLINE mode (fixture-based) rather than crashing.\n")
        mode = "offline"

    print("=" * 74)
    print(f"  Cascade AI eval pack — {len(SCENARIOS)} scenarios "
          f"(3 real incidents + 27 synthetic) — mode: {mode.upper()}")
    print("=" * 74)

    results = run_live(args.verbose) if mode == "live" else run_offline(args.verbose)

    passed = sum(1 for r in results if r["passed"])
    rate = passed / len(results)
    by_cat: dict[str, list] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r["passed"])

    print("\n" + "-" * 74)
    for cat, flags in sorted(by_cat.items()):
        print(f"  {cat:24} {sum(flags)}/{len(flags)}")
    print("-" * 74)
    print(f"  RESULT: {passed}/{len(results)} scenarios passed "
          f"({rate:.0%}; threshold {args.threshold:.0%})")
    gate_ok = rate >= args.threshold
    print(f"  GATE:   {'PASS ✅' if gate_ok else 'FAIL ❌ — blocking'}")
    print("=" * 74)

    if args.save:
        with open(args.save, "w") as f:
            json.dump({"mode": mode, "passed": passed, "total": len(results),
                       "pass_rate": rate, "threshold": args.threshold,
                       "results": results}, f, indent=2)
        print(f"  💾 saved {args.save}")

    return 0 if gate_ok else 1


if __name__ == "__main__":
    sys.exit(main())
