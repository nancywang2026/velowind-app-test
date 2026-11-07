import argparse
import json
import os
from pathlib import Path
from .config import ConfigError, load_config
from .http import ApiError
from .scenario import new_report, run
from .reporting import write_allure
from .console import log
from .report_viewer import open_report


def main():
    parser = argparse.ArgumentParser(description="Private chat API scenario (writes real test messages)")
    parser.add_argument("--data", required=True, help="External scenario JSON")
    parser.add_argument("--environment", help="Postman environment JSON (read only)")
    parser.add_argument("--check-config", action="store_true", help="Validate data without HTTP requests")
    parser.add_argument("--report", default=".tmp/private-chat-api/report.json")
    parser.add_argument("--alluredir", default=".tmp/private-chat-api/allure-results", help="Allure result directory (appended, never cleaned)")
    parser.add_argument("--open-report", action="store_true", help="Generate and open Allure after success or failure")
    parser.add_argument("--report-dir", help="Generated HTML directory; defaults to a sibling allure-report directory")
    args = parser.parse_args()
    report = new_report()
    exit_code = 0
    log("RUN", f"{'配置检查' if args.check_config else '私聊API测试'} run_id={report['run_id']}")
    try:
        config = load_config(args.data, args.environment)
        log("CONFIG", "配置校验通过")
        if args.check_config:
            report["status"] = "config_validated"
        else:
            run(config, report)
    except (ConfigError, ApiError, AssertionError) as exc:
        report["status"] = "blocked" if isinstance(exc, ConfigError) else "failed"
        report["error"] = str(exc)
        report["error_type"] = type(exc).__name__
        exit_code = 2 if isinstance(exc, ConfigError) else 1
    except Exception as exc:
        report["status"] = "failed"
        report["error_type"] = type(exc).__name__
        report["error"] = type(exc).__name__  # Never print third-party exception payloads.
        exit_code = 1
    finally:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as stream:
            os.chmod(target, 0o600)
            json.dump(report, stream, ensure_ascii=False, indent=2)
        write_allure(report, args.alluredir, config_only=args.check_config)
        if report.get("error"):
            log("ERROR", report["error"])
        log("RESULT", f"{report['status']}; allure-results={args.alluredir}; journal={target}")
        if args.open_report and not args.check_config:
            html_dir = args.report_dir or str(Path(args.alluredir).parent / "allure-report")
            if not open_report(args.alluredir, html_dir) and exit_code == 0:
                exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
