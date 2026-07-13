import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[4]
TEST_PATH = REPO_ROOT / "apps" / "velowind-app" / "appium" / "tests"
ALLURE_RESULTS = REPO_ROOT / ".tmp" / "appium-ios" / "allure-results"
ALLURE_REPORT = REPO_ROOT / ".tmp" / "appium-ios" / "allure-report"
DEFAULT_SUITE_FILE = REPO_ROOT / "apps" / "velowind-app" / "appium" / "test-suites" / "smoke.yaml"


@dataclass(frozen=True)
class TestSuite:
    tests: list[str]
    markers: list[str]
    pytest_args: list[str]


def _run(command):
    return subprocess.run(command, cwd=REPO_ROOT, check=False)


def _allure_pytest_args() -> list[str]:
    if importlib.util.find_spec("allure_pytest") is None:
        return []
    return [
        f"--alluredir={ALLURE_RESULTS}",
        "--clean-alluredir",
    ]


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


def load_test_suite(path: Path) -> TestSuite:
    raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw_data, dict):
        raise ValueError(f"Test suite file must contain a mapping: {path}")

    tests = raw_data.get("tests") or []
    markers = raw_data.get("markers") or []
    pytest_args = raw_data.get("pytest_args") or []

    for field_name, values in {
        "tests": tests,
        "markers": markers,
        "pytest_args": pytest_args,
    }.items():
        if not isinstance(values, list) or not all(isinstance(item, str) and item.strip() for item in values):
            raise ValueError(f"Test suite `{field_name}` must be a list of non-empty strings: {path}")

    if not tests and not markers:
        raise ValueError(f"Test suite must specify at least one test or marker: {path}")

    return TestSuite(
        tests=[item.strip() for item in tests],
        markers=[item.strip() for item in markers],
        pytest_args=[item.strip() for item in pytest_args],
    )


def _suite_test_paths(tests: list[str]) -> list[str]:
    return [str(TEST_PATH / test_path) for test_path in tests]


def build_pytest_command(cli_args: list[str]) -> list[str]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--suite")
    args, remaining = parser.parse_known_args(cli_args)

    base_command = [
        sys.executable,
        "-m",
        "pytest",
        str(TEST_PATH),
        "-q",
        *_allure_pytest_args(),
    ]

    if args.all:
        os.environ["VW_IOS_RUN_FULL"] = "true"
        return [*base_command, *remaining]

    if args.suite:
        suite = load_test_suite(Path(args.suite))
        suite_command = [*base_command]
        if suite.markers:
            suite_command.extend(["-m", " or ".join(suite.markers)])
        suite_command.extend(suite.pytest_args)
        suite_command.extend(_suite_test_paths(suite.tests))
        suite_command.extend(remaining)
        return suite_command

    return [*base_command, *(remaining or ["-m", "smoke"])]


def main() -> int:
    cli_args = sys.argv[1:]
    if not cli_args and DEFAULT_SUITE_FILE.exists():
        cli_args = ["--suite", str(DEFAULT_SUITE_FILE)]
    pytest_result = _run(build_pytest_command(cli_args))
    _generate_and_open_report()
    return pytest_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
