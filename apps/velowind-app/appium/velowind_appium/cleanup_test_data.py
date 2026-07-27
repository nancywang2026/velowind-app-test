import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Optional

from velowind_appium.android_config import load_android_config
from velowind_appium.android_driver import create_android_driver
from velowind_appium.cleanup import (
    CleanupReport,
    cleanup_activities,
    cleanup_notes,
    cleanup_sessions,
)
from velowind_appium.cleanup_config import load_cleanup_config
from velowind_appium.cleanup_config import CleanupConfig
from velowind_appium.config import load_ios_config
from velowind_appium.driver import create_ios_driver


VALID_PLATFORMS = {"ios", "android"}
VALID_INCLUDE = ("notes", "activities", "sessions")


def run_cleanup(platform: str, *, include: tuple[str, ...] = VALID_INCLUDE, dry_run: bool = False) -> list[CleanupReport]:
    cleanup_config = load_cleanup_config()
    if platform == "ios":
        app_config = load_ios_config()
        driver = create_ios_driver(app_config)
    elif platform == "android":
        app_config = load_android_config()
        driver = create_android_driver(app_config)
    else:
        raise ValueError(f"Unsupported cleanup platform: {platform}")

    try:
        reports: list[CleanupReport] = []
        if "notes" in include:
            reports.append(cleanup_notes(driver, cleanup_config, app_config, dry_run=dry_run))
        if "activities" in include:
            reports.append(cleanup_activities(driver, cleanup_config, app_config, dry_run=dry_run))
        if "sessions" in include:
            reports.append(cleanup_sessions(driver, cleanup_config, app_config, dry_run=dry_run))
        return reports
    finally:
        driver.quit()


def build_report_payload(
    *,
    platform: str,
    dry_run: bool,
    cleanup_config: CleanupConfig,
    reports: list[CleanupReport],
) -> dict:
    return {
        "platform": platform,
        "dry_run": dry_run,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "summary": [
            {
                "item_type": report.item_type,
                "deleted_count": len(report.deleted),
                "skipped_count": len(report.skipped),
            }
            for report in reports
        ],
        "reports": [
            {
                "item_type": report.item_type,
                "deleted": report.deleted,
                "skipped": report.skipped,
            }
            for report in reports
        ],
        "details": _report_details(reports, cleanup_config, dry_run=dry_run),
    }


def write_report_file(*, artifact_dir: Path, payload: dict) -> Path:
    report_dir = artifact_dir / "cleanup-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"cleanup-report-{datetime.now():%Y%m%d-%H%M%S}.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def _report_details(reports: list[CleanupReport], cleanup_config: CleanupConfig, *, dry_run: bool) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    for report in reports:
        matchers = _matchers_for_item_type(cleanup_config, report.item_type)
        deleted_action = "would_delete" if dry_run else "deleted"
        for text in report.deleted:
            details.append(_detail_entry(report.item_type, deleted_action, text, matchers))
        skipped_action = "would_delete" if dry_run else "skipped"
        for text in report.skipped:
            details.append(_detail_entry(report.item_type, skipped_action, text, matchers))
    return details


def _detail_entry(item_type: str, action: str, text: str, matchers: list[str]) -> dict[str, str]:
    return {
        "item_type": item_type,
        "action": action,
        "text": text,
        "matched_by": next((matcher for matcher in matchers if matcher in text), ""),
    }


def _matchers_for_item_type(cleanup_config: CleanupConfig, item_type: str) -> list[str]:
    if item_type == "note":
        return cleanup_config.note_matchers
    if item_type == "activity":
        return cleanup_config.activity_matchers
    if item_type == "session":
        return cleanup_config.session_matchers
    if item_type == "comment":
        return cleanup_config.comment_matchers
    return []


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Clean generated Appium test data through the app UI.")
    parser.add_argument("--platform", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include", nargs="+", choices=VALID_INCLUDE, default=list(VALID_INCLUDE))
    args = parser.parse_args(argv)

    if args.platform not in VALID_PLATFORMS:
        print(f"Unsupported platform: {args.platform}", file=sys.stderr)
        return 2

    cleanup_config = load_cleanup_config()
    reports = run_cleanup(
        args.platform,
        include=tuple(args.include),
        dry_run=args.dry_run,
    )
    artifact_dir = load_android_config().artifact_dir if args.platform == "android" else load_ios_config().artifact_dir
    report_path = write_report_file(
        artifact_dir=artifact_dir,
        payload=build_report_payload(
            platform=args.platform,
            dry_run=args.dry_run,
            cleanup_config=cleanup_config,
            reports=reports,
        ),
    )
    for report in reports:
        print(
            f"{report.item_type}: deleted={len(report.deleted)} skipped={len(report.skipped)}",
            flush=True,
        )
        for text in report.deleted:
            print(f"  deleted: {text}", flush=True)
        for text in report.skipped:
            print(f"  skipped: {text}", flush=True)
    print(f"cleanup report: {report_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
