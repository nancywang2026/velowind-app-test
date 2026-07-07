import shutil
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
TEST_PATH = REPO_ROOT / "apps" / "velowind-app" / "appium" / "tests" / "test_ios_feature_walkthrough.py"
ALLURE_RESULTS = REPO_ROOT / ".tmp" / "appium-ios" / "allure-results"
ALLURE_REPORT = REPO_ROOT / ".tmp" / "appium-ios" / "allure-report"


def _run(command):
    return subprocess.run(command, cwd=REPO_ROOT, check=False)


def _generate_and_open_report() -> None:
    allure_bin = shutil.which("allure")
    if allure_bin is None:
        print("Allure CLI not found. Install it with `brew install allure` to auto-open reports.")
        return
    if not ALLURE_RESULTS.exists():
        print(f"Allure results not found: {ALLURE_RESULTS}")
        return

    generate_result = _run(
        [
            allure_bin,
            "generate",
            str(ALLURE_RESULTS),
            "--clean",
            "-o",
            str(ALLURE_REPORT),
        ]
    )
    if generate_result.returncode != 0:
        return
    subprocess.Popen([allure_bin, "open", str(ALLURE_REPORT)], cwd=REPO_ROOT)


def main() -> int:
    marker_args = sys.argv[1:] or ["-m", "smoke"]
    if marker_args == ["--all"]:
        os.environ["VW_IOS_RUN_FULL"] = "true"
        marker_args = []
    pytest_result = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(TEST_PATH),
            "-q",
            *marker_args,
        ]
    )
    _generate_and_open_report()
    return pytest_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
