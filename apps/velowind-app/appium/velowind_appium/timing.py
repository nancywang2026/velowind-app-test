from __future__ import annotations

from contextlib import contextmanager
import os
import time
from typing import Callable, Iterator
from uuid import uuid4


TRUE_VALUES = {"1", "true", "yes", "y", "on"}
recorder = None


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
    active_recorder = recorder
    if not should_emit and active_recorder is None:
        yield
        return

    started_at = clock() if should_emit else None
    event_id = str(uuid4())
    if active_recorder is not None:
        active_recorder.start(event_id, label, "profile")
    status = "passed"
    try:
        yield
    except BaseException:
        status = "failed"
        raise
    finally:
        if active_recorder is not None:
            active_recorder.stop(event_id, status)
        if should_emit:
            elapsed = clock() - started_at
            emit(f"[appium-profile] {label} {elapsed:.2f}s")
