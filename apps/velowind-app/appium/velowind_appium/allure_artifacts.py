import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class AllureArtifacts:
    run_id: str
    results: Path
    report: Path
    latest_report: Path


def default_run_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{os.getpid()}"


def ensure_run_id() -> str:
    run_id = os.environ.get("VW_APPIUM_RUN_ID", "").strip()
    if run_id:
        return run_id
    run_id = default_run_id()
    os.environ["VW_APPIUM_RUN_ID"] = run_id
    return run_id


def _env_path(name: str) -> Optional[Path]:
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser() if value else None


def allure_artifacts(repo_root: Path, platform: str, run_id: Optional[str] = None) -> AllureArtifacts:
    resolved_run_id = run_id or ensure_run_id()
    platform_dir = repo_root / ".tmp" / f"appium-{platform}"
    run_dir = platform_dir / "runs" / resolved_run_id
    return AllureArtifacts(
        run_id=resolved_run_id,
        results=_env_path("VW_ALLURE_RESULTS_DIR") or run_dir / "allure-results",
        report=_env_path("VW_ALLURE_REPORT_DIR") or run_dir / "allure-report",
        latest_report=platform_dir / "latest-report",
    )
