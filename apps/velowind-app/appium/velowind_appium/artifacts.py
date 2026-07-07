from datetime import datetime
from pathlib import Path
import re


def ensure_artifact_dir(base_dir: Path) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def safe_name(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip())
    return normalized.strip("-") or "artifact"


def timestamped_path(base_dir: Path, label: str, suffix: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return ensure_artifact_dir(base_dir) / f"{stamp}-{safe_name(label)}.{suffix.lstrip('.')}"
