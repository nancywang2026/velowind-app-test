from __future__ import annotations

from contextlib import contextmanager
import os
import time
from typing import Callable, Iterator


TRUE_VALUES = {"1", "true", "yes", "y", "on"}


def env_flag_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUE_VALUES


@contextmanager
def profile_section(
    label: str,
    *,
    enabled: bool | None = None,
    emit: Callable[[str], None] = print,
    clock: Callable[[], float] = time.monotonic,
) -> Iterator[None]:
    should_emit = env_flag_enabled("VW_APPIUM_PROFILE") if enabled is None else enabled
    if not should_emit:
        yield
        return

    started_at = clock()
    try:
        yield
    finally:
        elapsed = clock() - started_at
        emit(f"[appium-profile] {label} {elapsed:.2f}s")
