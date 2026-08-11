import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from .allure_artifacts import allure_artifacts as _resolve_allure_artifacts


REPO_ROOT = Path(__file__).resolve().parents[4]
TEST_PATH = REPO_ROOT / "apps" / "velowind-app" / "appium" / "tests"
DEFAULT_SUITE_FILE = REPO_ROOT / "apps" / "velowind-app" / "appium" / "test-suites" / "smoke.yaml"
SUITE_PROFILE_FILES = {
    "smoke": DEFAULT_SUITE_FILE,
    "publish": REPO_ROOT / "apps" / "velowind-app" / "appium" / "test-suites" / "ios-message-publish.yaml",
    "full": REPO_ROOT / "apps" / "velowind-app" / "appium" / "test-suites" / "ios-full.yaml",
}


@dataclass(frozen=True)
class TestSuite:
    tests: list[str]
    markers: list[str]
    pytest_args: list[str]


def _run(command):
    return subprocess.run(command, cwd=REPO_ROOT, check=False)


def allure_artifacts(run_id=None):
    return _resolve_allure_artifacts(REPO_ROOT, "ios", run_id)


def _allure_pytest_args(*, clean: bool = True) -> list[str]:
    if importlib.util.find_spec("allure_pytest") is None:
        return []
    artifacts = allure_artifacts()
    args = [f"--alluredir={artifacts.results}"]
    if clean:
        args.append("--clean-alluredir")
    return args


def _generate_and_open_report() -> None:
    artifacts = allure_artifacts()
    allure_bin = shutil.which("allure")
    if allure_bin is None:
        print("Allure CLI not found. Install it with `brew install allure` to auto-open reports.")
        return
    if not artifacts.results.exists():
        print(f"Allure results not found: {artifacts.results}")
        return

    generate_result = _run(
        [
            allure_bin,
            "generate",
            str(artifacts.results),
            "--clean",
            "-o",
            str(artifacts.report),
        ]
    )
    if generate_result.returncode != 0:
        return
    try:
        if artifacts.latest_report.exists() or artifacts.latest_report.is_symlink():
            artifacts.latest_report.unlink()
        artifacts.latest_report.symlink_to(artifacts.report, target_is_directory=True)
    except OSError:
        pass
    open_command = [allure_bin, "open", str(artifacts.report)]
    port = os.environ.get("VW_ALLURE_OPEN_PORT", "").strip()
    if port:
        open_command.extend(["-p", port])
    subprocess.Popen(open_command, cwd=REPO_ROOT)


def load_test_suite(path: Path) -> TestSuite:
    raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw_data, dict):
        raise ValueError(f"Test suite file must contain a mapping: {path}")

    tests = raw_data.get("tests") or []
    markers = raw_data.get("markers") or []
    pytest_args = raw_data.get("pytest_args") or []

    for field_name, values in {"markers": markers, "pytest_args": pytest_args}.items():
        if not isinstance(values, list) or not all(isinstance(item, str) and item.strip() for item in values):
            raise ValueError(f"Test suite `{field_name}` must be a list of non-empty strings: {path}")

    normalized_tests = _normalize_suite_tests(tests, path)

    if not normalized_tests and not markers:
        raise ValueError(f"Test suite must specify at least one test or marker: {path}")

    return TestSuite(
        tests=normalized_tests,
        markers=[item.strip() for item in markers],
        pytest_args=[item.strip() for item in pytest_args],
    )


def _normalize_suite_tests(tests: object, path: Path) -> list[str]:
    if not isinstance(tests, list):
        raise ValueError(f"Test suite `tests` must be a list: {path}")

    normalized: list[str] = []
    for item in tests:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
            continue
        if isinstance(item, dict):
            file_path = item.get("file")
            methods = item.get("methods")
            if not isinstance(file_path, str) or not file_path.strip():
                raise ValueError(f"Test suite `tests[].file` must be a non-empty string: {path}")
            if not isinstance(methods, list) or not all(isinstance(method, str) and method.strip() for method in methods):
                raise ValueError(f"Test suite `tests[].methods` must be a list of non-empty strings: {path}")
            normalized.extend(f"{file_path.strip()}::{method.strip()}" for method in methods)
            continue
        raise ValueError(f"Test suite `tests` must contain strings or file/methods mappings: {path}")
    return normalized


def _suite_test_paths(tests: list[str]) -> list[str]:
    return [str(TEST_PATH / test_path) for test_path in tests]


def _env_flag_enabled(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def retry_failed_enabled(cli_args: list[str]) -> bool:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--retry-failed", action="store_true")
    args, _ = parser.parse_known_args(cli_args)
    return args.retry_failed or _env_flag_enabled("VW_APPIUM_RETRY_FAILED")


def build_pytest_command(
    cli_args: list[str],
    *,
    clean_allure: bool = True,
    last_failed: bool = False,
    run_all_failures: bool = False,
) -> list[str]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--suite")
    parser.add_argument("--suite-profile", choices=sorted(SUITE_PROFILE_FILES))
    parser.add_argument("--retry-failed", action="store_true")
    args, remaining = parser.parse_known_args(cli_args)

    base_command = [
        sys.executable,
        "-m",
        "pytest",
        str(TEST_PATH),
        "-q",
        "-s",
        *_allure_pytest_args(clean=clean_allure),
    ]
    if last_failed:
        base_command.append("--lf")
    if run_all_failures:
        base_command.append("--maxfail=0")

    if args.all:
        os.environ["VW_IOS_RUN_FULL"] = "true"
        return [*base_command, *remaining]

    if args.suite and args.suite_profile:
        raise ValueError("Use either --suite or --suite-profile, not both.")

    suite_file = Path(args.suite) if args.suite else SUITE_PROFILE_FILES.get(args.suite_profile)
    if suite_file:
        suite = load_test_suite(suite_file)
        suite_command = [*base_command]
        if suite.markers:
            suite_command.extend(["-m", " or ".join(suite.markers)])
        suite_command.extend(suite.pytest_args)
        suite_command.extend(_suite_test_paths(suite.tests))
        suite_command.extend(remaining)
        return suite_command

    return [*base_command, *(remaining or ["-m", "smoke"])]


def main() -> int:
    allure_artifacts()
    cli_args = sys.argv[1:]
    if not cli_args and DEFAULT_SUITE_FILE.exists():
        cli_args = ["--suite", str(DEFAULT_SUITE_FILE)]
    retry_enabled = retry_failed_enabled(cli_args)
    pytest_result = _run(build_pytest_command(cli_args, clean_allure=True, run_all_failures=retry_enabled))
    if pytest_result.returncode == 1 and retry_enabled:
        print("Retrying failed pytest cases with --lf before generating Allure report.")
        pytest_result = _run(
            build_pytest_command(cli_args, clean_allure=False, last_failed=True, run_all_failures=True)
        )
    _generate_and_open_report()
    return pytest_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
