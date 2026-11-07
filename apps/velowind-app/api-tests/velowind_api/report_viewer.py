"""Generate and launch Allure without keeping the test command running."""
import shutil
import subprocess
from pathlib import Path
from .console import log


def open_report(results_dir, report_dir):
    executable = shutil.which("allure")
    if not executable:
        log("REPORT", "未找到 allure 命令；原始结果已保留，请安装 Allure CLI 后生成报告")
        return False
    results = Path(results_dir).resolve()
    report = Path(report_dir).resolve()
    # Allure --clean must never remove results or a parent containing results.
    if report == results or report in results.parents:
        log("REPORT", "报告目录不能等于或包含原始结果目录")
        return False
    try:
        log("REPORT", "正在生成 Allure HTML 报告")
        subprocess.run([executable, "generate", str(results), "-o", str(report), "--clean"],
                       check=True, capture_output=True, text=True, timeout=60)
        # Keep the server log for troubleshooting; no credentials or bodies here.
        with (report / "viewer.log").open("ab") as stream:
            subprocess.Popen([executable, "open", str(report)], stdin=subprocess.DEVNULL,
                             stdout=stream, stderr=stream, start_new_session=True)
        log("REPORT", f"Allure 浏览器已启动；报告目录={report}")
        return True
    except (OSError, subprocess.SubprocessError) as exc:
        log("REPORT", f"报告生成或启动失败（{type(exc).__name__}）；原始结果已保留")
        return False
