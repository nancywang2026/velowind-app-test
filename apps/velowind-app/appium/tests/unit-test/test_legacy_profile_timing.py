import json

import pytest

from velowind_appium import timing
from velowind_appium.modules import activity, message_detail, photo_picker
from velowind_appium.pytest_timing import TimingRecorder


@pytest.mark.parametrize("context,prefix", [
    (message_detail._note_profile, "note"),
    (activity._activity_profile, "activity"),
    (photo_picker._photo_picker_profile, "photo-picker"),
])
@pytest.mark.parametrize("fails", [False, True])
def test_legacy_stage_is_persisted_even_without_console_profiling(tmp_path, monkeypatch, context, prefix, fails):
    monkeypatch.delenv("VW_ACTIVITY_PROFILE", raising=False)
    monkeypatch.delenv("VW_APPIUM_PROFILE", raising=False)
    recorder = TimingRecorder(tmp_path / "timing", {})
    monkeypatch.setattr(timing, "recorder", recorder)
    recorder.begin("sample", "sample")
    error = RuntimeError("original failure")
    try:
        if fails:
            with pytest.raises(RuntimeError) as caught:
                with context("stage"):
                    raise error
            assert caught.value is error
        else:
            with context("stage"):
                pass
        recorder.end()
        report = json.loads((recorder.output / "timings.json").read_text())
        step = report["cases"][0]["steps"][0]
        assert step["name"] == f"{prefix}.stage"
        assert step["status"] == ("failed" if fails else "passed")
        assert step["duration_seconds"] >= 0
        assert recorder.active == {}
    finally:
        recorder.stream.close()
