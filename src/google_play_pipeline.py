"""Collect and describe unfiltered Google Play reviews.

The default command asks for confirmation before any Play request.
Analysis can be repeated from the saved CSV without a network request.

    python -m src.google_play_pipeline
    python -m src.google_play_pipeline --analyze-only

This module does not call Gemini. It does not change
data/raw/sip_relevant_reviews.csv.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.google_play_analyze import (
    ANALYSIS_COLUMNS,
    annotate_reviews,
    build_comparative_report,
    build_quality_report,
    category_counts,
    evidence_rows,
)
from src.google_play_clean import CLEAN_COLUMNS, clean_reviews, read_raw_reviews, write_csv
from src.google_play_collect import (
    APPS,
    MAX_REVIEWS,
    RAW_COLUMNS,
    RAW_OUTPUT,
    CollectionError,
    collect_apps,
    output_is_blocked,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MASTER_PATH = PROJECT_ROOT / "data" / "processed" / "google_play_reviews_master.csv"
EVIDENCE_PATH = PROJECT_ROOT / "data" / "processed" / "google_play_sip_evidence.csv"
QUALITY_PATH = PROJECT_ROOT / "data" / "processed" / "google_play_quality_report.md"
COMPARATIVE_PATH = PROJECT_ROOT / "data" / "processed" / "google_play_comparative_analysis.md"
CATEGORY_PATH = PROJECT_ROOT / "data" / "processed" / "google_play_problem_categories.csv"

DERIVED_OUTPUTS = (
    MASTER_PATH,
    EVIDENCE_PATH,
    QUALITY_PATH,
    COMPARATIVE_PATH,
    CATEGORY_PATH,
)
CATEGORY_COLUMNS = ("app_name", "possible_problem_category", "review_count")


def confirm_collection(lines: list[str]) -> bool:
    """Show the plan and wait for YES. Any other answer cancels."""
    print("Google Play collection plan:")
    for line in lines:
        print(line)
    print("No Play request has been made yet.")
    if not sys.stdin.isatty():
        print("Cancelled. This command needs an interactive terminal so you can confirm.")
        return False
    answer = input("Type YES to start collection. Anything else cancels: ")
    if answer.strip() != "YES":
        print("Cancelled. No reviews were collected and no reports were written.")
        return False
    return True


def write_derived(annotated: list[dict[str, str]], clean_result: dict, replace: bool) -> tuple[list[str], list[str]]:
    """Write reports from rows already in memory. Existing files are kept unless replace is set."""
    written = []
    skipped = []
    targets = (
        (MASTER_PATH, "csv-master"),
        (EVIDENCE_PATH, "csv-evidence"),
        (QUALITY_PATH, "md-quality"),
        (COMPARATIVE_PATH, "md-compare"),
        (CATEGORY_PATH, "csv-categories"),
    )
    for path, kind in targets:
        if path.exists() and not replace:
            skipped.append(str(path))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "csv-master":
            write_csv(annotated, path, ANALYSIS_COLUMNS)
        elif kind == "csv-evidence":
            write_csv(evidence_rows(annotated), path, ANALYSIS_COLUMNS)
        elif kind == "md-quality":
            path.write_text(build_quality_report(clean_result, annotated), encoding="utf-8")
        elif kind == "md-compare":
            path.write_text(build_comparative_report(annotated), encoding="utf-8")
        else:
            write_csv(category_counts(annotated), path, CATEGORY_COLUMNS)
        written.append(str(path))
    return written, skipped


def run_analysis(raw_path: Path, replace_reports: bool) -> dict:
    """Clean and label the saved reviews. This does not contact Google Play."""
    raw_rows = read_raw_reviews(raw_path)
    clean_result = clean_reviews(raw_rows)
    annotated = annotate_reviews(clean_result["rows"])
    written, skipped = write_derived(annotated, clean_result, replace=replace_reports)
    return {
        "raw_rows": len(raw_rows),
        "kept": len(annotated),
        "evidence": len(evidence_rows(annotated)),
        "written": written,
        "skipped": skipped,
        "apps": sorted({row.get("app_name", "") for row in annotated}),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect or analyse unfiltered Google Play reviews.")
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Rebuild the processed reports from the saved unfiltered CSV. Does not use the network.",
    )
    return parser.parse_args()


def main() -> None:
    """Ask before downloading. Refuse to replace an existing raw download."""
    args = parse_args()
    if args.analyze_only:
        if not RAW_OUTPUT.is_file():
            print(f"Error: {RAW_OUTPUT} is not available, so there is nothing to analyse.", file=sys.stderr)
            sys.exit(1)
        try:
            summary = run_analysis(RAW_OUTPUT, replace_reports=True)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"Analysed {summary['kept']} reviews from {summary['raw_rows']} raw rows.")
        print(f"Evidence leads: {summary['evidence']}")
        for path in summary["written"]:
            print(f"Wrote {path}")
        return

    if output_is_blocked(RAW_OUTPUT):
        print(
            f"Stopped. {RAW_OUTPUT} already exists, so it was not overwritten. "
            "Use --analyze-only to rebuild the reports from that file.",
            file=sys.stderr,
        )
        sys.exit(1)

    plan = [
        "Country: India. Language: English. Sort: newest.",
        f"Maximum reviews per app: {MAX_REVIEWS}. Reviews are not filtered by keyword.",
        "Apps:",
    ]
    for app_name, package_id in APPS:
        plan.append(f"  {app_name}: {package_id}")
    plan.append(f"Raw output, written only after all three apps succeed: {RAW_OUTPUT}")
    if not confirm_collection(plan):
        sys.exit(1)

    try:
        collected = collect_apps(max_reviews=MAX_REVIEWS)
    except CollectionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("No raw file and no reports were written.", file=sys.stderr)
        sys.exit(1)

    if not collected["complete"]:
        print("Collection did not finish for every app. No raw file and no reports were written.")
        for app_name, _package_id in APPS:
            if app_name in collected["app_counts"]:
                print(f"  fetched but not saved: {app_name} ({collected['app_counts'][app_name]} reviews)")
        for app_name, detail in collected["failures"]:
            print(f"  failed: {app_name}: {detail}")
        sys.exit(1)

    write_csv(collected["rows"], RAW_OUTPUT, RAW_COLUMNS)
    print(f"Wrote {RAW_OUTPUT}")
    for app_name, _package_id in APPS:
        print(f"  {app_name}: {collected['app_counts'].get(app_name, 0)} reviews")

    summary = run_analysis(RAW_OUTPUT, replace_reports=False)
    print(f"Cleaned reviews: {summary['kept']}")
    print(f"Evidence leads: {summary['evidence']}")
    for path in summary["written"]:
        print(f"Wrote {path}")
    for path in summary["skipped"]:
        print(f"Skipped existing derived file: {path}")


if __name__ == "__main__":
    main()
