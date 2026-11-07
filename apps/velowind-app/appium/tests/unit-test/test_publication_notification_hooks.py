from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from tests import shared_publish_note as notes
from tests.activity import test_publish_activity as activities


def test_note_notification_runs_between_single_publish_and_cleanup_even_on_failure(monkeypatch):
    events=[]
    draft=SimpleNamespace(title="this-run",topics=[],location="test",allow_comments=True,media_source="album")
    monkeypatch.setattr(notes,"load_message_note_draft",lambda *a,**k:draft)
    monkeypatch.setattr(notes,"ensure_logged_in_for_publish_entry",lambda *a:None)
    monkeypatch.setattr(notes,"publish_message_note",lambda *a,**k:events.append("publish") or "待审核")
    monkeypatch.setattr(notes,"attach_text",lambda *a:None)
    monkeypatch.setattr(notes,"load_cleanup_config",lambda:SimpleNamespace(delete_published_note_after_success=True))
    monkeypatch.setattr(notes,"cleanup_published_note_after_success",lambda *a:events.append("cleanup"))
    observer=Mock()
    observer.before_business.side_effect=lambda:events.append("baseline")
    def notification(*args):
        events.append("notification")
        # Pending is handed to the observer, never asserted as notification success.
        assert args[-1]=="待审核"
        raise AssertionError("publication not yet approved")
    observer.after_publication.side_effect=notification
    with pytest.raises(AssertionError,match="not yet"):
        notes.run_publish_note_case(object(),object(),lambda name,action:action(),"case",
             verification_label="verify",assertion_label="iOS",notification_observer=observer)
    assert events==["baseline","publish","notification","cleanup"]


def test_activity_publication_reuses_single_business_action_before_notification(monkeypatch):
    events=[];draft=object()
    monkeypatch.setattr(activities,"build_activity_draft",lambda:draft)
    monkeypatch.setattr(activities,"dismiss_common_system_alerts",lambda *a:None)
    monkeypatch.setattr(activities,"ensure_logged_in_for_publish_entry",lambda *a:None)
    monkeypatch.setattr(activities,"publish_activity",lambda *a,**k:events.append("publish") or "待审核")
    monkeypatch.setattr(activities,"attach_text",lambda *a:None)
    observer=Mock()
    observer.before_business.side_effect=lambda:events.append("baseline")
    observer.after_publication.side_effect=lambda *a:events.append("notification")
    activities.run_publish_activity_case(object(),object(),lambda name,action:action(),notification_observer=observer)
    assert events==["baseline","publish","notification"]


def test_concrete_post_observer_never_moderates_preexisting_matching_title(monkeypatch):
    from velowind_appium.message_regression.publication import PostPublicationObserver
    from velowind_appium.message_regression.core import Actor,Blocked
    import velowind_appium.message_regression.core as core
    actor=Actor('c','C','private-token');api=Mock()
    old={'postId':'old','title':'same-title','createdAtEpochMillis':9999999999999}
    api.pages.return_value=[old]
    observer=PostPublicationObserver(api,actor,actor,Mock())
    observer.hook=Mock();observer.before_business()
    def no_wait(query,predicate,**kwargs):
        value=query()
        if not predicate(value):raise Blocked('No current publication')
        return value
    monkeypatch.setattr(core,'wait',no_wait)
    with pytest.raises(Blocked,match='No current'):
        observer.after_publication(None,None,SimpleNamespace(title='same-title',body='text'),'待审核')
    api.request.assert_not_called()
