from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from tests.activity import test_ios_activity_browse as signup
from velowind_appium.message_regression.enrollment import EnrollmentObserver
from velowind_appium.message_regression.core import Actor


def prepare_existing_case(monkeypatch,submit):
    for name in ('build_activity_signup_draft','dismiss_common_system_alerts','ensure_logged_in_on_home',
                 'open_activity_tab','wait_for_activity_feed','_open_signup_available_activity_detail_or_skip',
                 'open_activity_signup','fill_activity_signup_form'):
        monkeypatch.setattr(signup,name,lambda *args,**kwargs:None)
    monkeypatch.setattr(signup,'submit_activity_signup_order',submit)


def test_signup_notification_failure_still_cleans_same_single_signup(monkeypatch):
    events=[]
    snapshot=SimpleNamespace(is_order_submission_complete=lambda:True)
    prepare_existing_case(monkeypatch,lambda *a,**k:events.append('submit') or snapshot)
    observer=Mock()
    observer.before_business.side_effect=lambda:events.append('baseline')
    def failed(*args):events.append('notification');raise AssertionError('missing current notification')
    observer.after_signup.side_effect=failed
    observer.cleanup.side_effect=lambda:events.append('cleanup')
    with pytest.raises(AssertionError,match='missing current'):
        signup.run_activity_signup_case(SimpleNamespace(page_source=''),object(),lambda name,action,**kwargs:action(),notification_observer=observer)
    assert events==['baseline','submit','notification','cleanup']


def test_unknown_signup_submit_is_not_retried_and_cleanup_runs(monkeypatch):
    submit=Mock(side_effect=TimeoutError('unknown submit result'))
    prepare_existing_case(monkeypatch,submit)
    observer=Mock()
    with pytest.raises(TimeoutError):
        signup.run_activity_signup_case(SimpleNamespace(page_source=''),object(),lambda name,action,**kwargs:action(),notification_observer=observer)
    submit.assert_called_once()
    observer.after_signup.assert_not_called()
    observer.cleanup.assert_called_once()


def test_enrollment_cleanup_never_cancels_old_baseline_order():
    actor=Actor('actor','Test','private-token');api=Mock()
    api.pages.return_value=[{'enrollmentId':'old','createdAtEpochMillis':9999999999999}]
    observer=EnrollmentObserver(api,actor,Mock())
    observer.messages=Mock();observer.messages.notifications.return_value=[]
    observer.before_business()
    assert observer.cleanup()['status']=='no-current-signup-found'
    api.request.assert_not_called()


def test_paid_enrollment_cleanup_does_not_claim_failed_refund_is_clean():
    actor=Actor('actor','Test','private-token');api=Mock()
    observer=EnrollmentObserver(api,actor,Mock())
    observer.existing_ids=set();observer.enrollment_id='current'
    observer.current=Mock(return_value={'enrollmentStatus':'REFUND_FAILED','paymentStatus':'SUCCEEDED','refundStatus':'FAILED'})
    with pytest.raises(AssertionError,match='cleanup-pending'):observer.cleanup()
    assert observer.cleanup_status!='business-cancelled-or-rejected'
