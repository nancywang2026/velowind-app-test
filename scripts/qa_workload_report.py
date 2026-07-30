from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APPIUM_ROOT = REPO_ROOT / "apps" / "velowind-app" / "appium"
sys.path.insert(0, str(APPIUM_ROOT))

from velowind_appium.qa_workload_report import main


if __name__ == "__main__":
    raise SystemExit(main())
