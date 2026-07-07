from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


try:
    import allure as _allure
except ModuleNotFoundError:  # pragma: no cover - local fallback for lightweight collection/unit runs
    class _AllureFallback:
        class attachment_type:
            PNG = "png"
            XML = "xml"
            TEXT = "text"

        class attach:
            @staticmethod
            def file(*args, **kwargs):
                return None

            @staticmethod
            def body(*args, **kwargs):
                return None

        @staticmethod
        def step(title):
            class _StepContext:
                def __enter__(self):
                    return title

                def __exit__(self, exc_type, exc, tb):
                    return False

            return _StepContext()

    _allure = _AllureFallback()


allure = _allure


def attach_file_if_present(path: Path | None, *, name: str | None = None, attachment_type=None) -> None:
    if path is None or not path.exists():
        return
    allure.attach.file(
        str(path),
        name=name or path.name,
        attachment_type=attachment_type,
    )


def attach_text(name: str, body: str) -> None:
    allure.attach.body(body, name=name, attachment_type=allure.attachment_type.TEXT)


def generate_and_open_allure_report(
    *,
    repo_root: Path,
    allure_results: Path,
    allure_report: Path,
    auto_open_env: str = "VW_APPIUM_AUTO_OPEN_REPORT",
) -> bool:
    if os.environ.get(auto_open_env) != "true":
        return False

    allure_bin = shutil.which("allure")
    if allure_bin is None or not allure_results.exists():
        return False

    generate_result = subprocess.run(
        [
            allure_bin,
            "generate",
            str(allure_results),
            "--clean",
            "-o",
            str(allure_report),
        ],
        cwd=repo_root,
        check=False,
    )
    if generate_result.returncode != 0:
        return False

    subprocess.Popen([allure_bin, "open", str(allure_report)], cwd=repo_root)
    return True
