"""Carry Allure 2 history between isolated run directories."""
from __future__ import annotations

from pathlib import Path
import shutil


def prepare_history(results: Path, report: Path, latest_report: Path | None = None) -> None:
    # Keep the original input on regeneration: inheriting our own output duplicates a run.
    target = results / "history"
    if target.exists():
        return
    candidates = list(report.parent.parent.glob("*/allure-report"))
    if latest_report is not None and latest_report.exists():
        candidates.append(latest_report.resolve())
    cutoff = min((p.stat().st_mtime for p in results.glob("*-result.json")), default=results.stat().st_mtime)
    previous = []
    for candidate in candidates:
        if candidate.resolve() == report.resolve():
            continue
        history = candidate / "history"
        if history.is_dir() and history.stat().st_mtime <= cutoff:
            previous.append(history)
    if previous:
        shutil.copytree(max(previous, key=lambda path: path.stat().st_mtime), target)


def update_latest(report: Path, latest_report: Path) -> None:
    if latest_report.exists() and not latest_report.is_symlink():
        return
    temporary = latest_report.with_name(latest_report.name + ".new")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(report.resolve(), target_is_directory=True)
    temporary.replace(latest_report)


def main() -> int:
    import argparse
    import os
    import subprocess
    from .allure_artifacts import allure_artifacts

    parser = argparse.ArgumentParser(description="Generate an Allure report with previous run history")
    parser.add_argument("--platform", choices=["ios", "android"], required=True)
    args = parser.parse_args()
    if not os.environ.get("VW_APPIUM_RUN_ID", "").strip():
        parser.error("VW_APPIUM_RUN_ID is required")
    root = Path(__file__).resolve().parents[4]
    artifacts = allure_artifacts(root, args.platform)
    if not artifacts.results.is_dir():
        parser.error(f"Allure results not found: {artifacts.results}")
    prepare_history(artifacts.results, artifacts.report, artifacts.latest_report)
    result = subprocess.run(["allure", "generate", str(artifacts.results), "--clean", "-o", str(artifacts.report)], cwd=root)
    if result.returncode == 0:
        update_latest(artifacts.report, artifacts.latest_report)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
