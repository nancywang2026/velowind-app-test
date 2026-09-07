from types import SimpleNamespace

from selenium.common.exceptions import TimeoutException

from velowind_appium.cleanup import CleanupReport

from tests import shared_publish_note


def _run_case(monkeypatch, *, cleanup_enabled: bool) -> list[str]:
    draft = SimpleNamespace(
        title="测试 - 长白山",
        topics=["骑行"],
        location="长白山",
        allow_comments=True,
        media_source="album",
    )
    events: list[str] = []
    monkeypatch.setattr(shared_publish_note, "load_message_note_draft", lambda *args, **kwargs: draft)
    monkeypatch.setattr(shared_publish_note, "ensure_logged_in_for_publish_entry", lambda *args: None)
    monkeypatch.setattr(shared_publish_note, "publish_message_note", lambda *args, **kwargs: "发布成功")
    monkeypatch.setattr(shared_publish_note, "attach_text", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        shared_publish_note,
        "load_cleanup_config",
        lambda: SimpleNamespace(delete_published_note_after_success=cleanup_enabled),
    )
    monkeypatch.setattr(
        shared_publish_note,
        "cleanup_published_note",
        lambda *args: events.append("delete") or CleanupReport("note", [draft.title], []),
    )

    def step(name, action):
        events.append(name)
        return action()

    shared_publish_note.run_publish_note_case(
        object(),
        object(),
        step,
        "publish-note-changbaishan",
        verification_label="publish-note-verification",
        assertion_label="iOS",
    )
    return events


def test_run_publish_note_case_cleans_up_after_success_when_enabled(monkeypatch):
    events = _run_case(monkeypatch, cleanup_enabled=True)

    assert events == [
        "prepare-home-session",
        "publish-note-for-review-publish-note-changbaishan",
        "cleanup-published-note-publish-note-changbaishan",
        "delete",
    ]


def test_run_publish_note_case_keeps_note_when_cleanup_is_disabled(monkeypatch):
    events = _run_case(monkeypatch, cleanup_enabled=False)

    assert events == [
        "prepare-home-session",
        "publish-note-for-review-publish-note-changbaishan",
    ]


def test_cleanup_retries_until_pending_note_is_deletable(monkeypatch):
    reports = iter(
        [
            CleanupReport("note", [], []),
            CleanupReport("note", ["测试 - 长白山"], []),
        ]
    )
    monkeypatch.setattr(
        shared_publish_note,
        "cleanup_published_note",
        lambda *args: next(reports),
    )
    monkeypatch.setattr(shared_publish_note.time, "sleep", lambda seconds: None)

    shared_publish_note.cleanup_published_note_after_success(
        object(),
        object(),
        "测试 - 长白山",
        timeout=1,
    )

    assert list(reports) == []


def test_cleanup_retries_when_ios_hierarchy_is_temporarily_unavailable(monkeypatch):
    attempts = iter(
        [
            TimeoutException("Home feed did not become ready; page_source=<empty>"),
            CleanupReport("note", ["测试 - 长白山"], []),
        ]
    )

    def cleanup(*args):
        result = next(attempts)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(shared_publish_note, "cleanup_published_note", cleanup)
    monkeypatch.setattr(shared_publish_note.time, "sleep", lambda seconds: None)

    shared_publish_note.cleanup_published_note_after_success(
        object(),
        object(),
        "测试 - 长白山",
        timeout=1,
    )

    assert list(attempts) == []


def test_cleanup_does_not_fail_publish_when_reviewing_note_is_not_listed(monkeypatch):
    attachments = []
    monkeypatch.setattr(
        shared_publish_note,
        "cleanup_published_note",
        lambda *args: CleanupReport("note", [], []),
    )
    monkeypatch.setattr(shared_publish_note.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        shared_publish_note,
        "attach_text",
        lambda name, body: attachments.append((name, body)),
    )

    report = shared_publish_note.cleanup_published_note_after_success(
        object(),
        object(),
        "Velowind｜解锁轻松骑行状态 🚲",
        timeout=0,
    )

    assert report == CleanupReport("note", [], [])
    assert attachments == [
        (
            "publish-note-cleanup-pending",
            "title=Velowind｜解锁轻松骑行状态 🚲\ndeleted=[]\nskipped=[]",
        )
    ]
