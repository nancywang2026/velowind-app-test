"""Concrete API cases, independent of the legacy operations JSON bindings.

Enable VW_MESSAGE_LIVE_API=1. Native verification has its own owned-session CLI.
Each lifecycle uses one fixture and one group; cases share only that run's data.
"""
import os
from pathlib import Path
import uuid
import pytest

from velowind_appium.message_regression.live import LiveRun
from velowind_appium.message_regression.interactions import comment_notifications

GROUP_CASES=(
 'group.create-and-member-list','group.invite-accept-reject','group.reinvite-and-search-members',
 'group.pin-mute-per-user-persistence','group.rename-and-announcement','group.member-cannot-rename',
 'group.member-cannot-announcement','group.member-cannot-dissolve','group.rejected-owner-operations-preserve-state',
 'group.text-order-and-older-pagination','group.image-bidirectional-full-bytes','group.read-and-own-history-clear',
 'group.remove-member-and-exit',
)
COMMENT_CASES=('comments.existing-owned-post-preparation','comments.publish-real-mention-and-notification',
 'comments.reply-and-notification','comments.like-and-notification','comments.favorite-and-notification')


def new_run(suite):
    if os.getenv('VW_MESSAGE_LIVE_API')!='1':pytest.skip('Live message API writes require VW_MESSAGE_LIVE_API=1')
    accounts=os.getenv('VW_MESSAGE_ACCOUNTS')
    if not accounts:pytest.fail('Set VW_MESSAGE_ACCOUNTS to private grouped A/B/C account JSON')
    root=Path(os.getenv('VW_MESSAGE_REPORT_DIR','outputs/message-live'))/suite/uuid.uuid4().hex
    return LiveRun(accounts,root)


@pytest.fixture(scope='module')
def live_groups():
    run=new_run('groups')
    try:run.groups(images=True)
    except Exception as exc:
        if not any(x['status'] in ('failed','blocked') for x in run.report['cases']):
            pytest.fail('Unrecorded group execution failure: '+type(exc).__name__)
    run.save()
    return run


@pytest.fixture(scope='module')
def live_comments():
    post_id=os.getenv('VW_MESSAGE_EXISTING_POST_ID')
    if not post_id:pytest.skip('Reuse an existing C-owned published note via VW_MESSAGE_EXISTING_POST_ID')
    run=new_run('comments')
    try:comment_notifications(run,post_id)
    except Exception as exc:
        if not any(x['status'] in ('failed','blocked') for x in run.report['cases']):
            pytest.fail('Unrecorded comment execution failure: '+type(exc).__name__)
    run.save()
    return run


def assert_case(run,name):
    rows=[x for x in run.report['cases'] if x['name']==name]
    if not rows:
        assert any(x['status'] in ('failed','blocked') for x in run.report['cases']), 'Case was never executed'
        pytest.skip('Dependency failed before this case; inspect live-results.json')
    row=rows[0]
    if row['status']=='blocked':pytest.skip('BLOCKED: '+row.get('reason','Missing execution prerequisite'))
    assert row['status']=='passed',f"{name}: {row}; report={run.output}/live-results.json"


@pytest.mark.parametrize('case_name',GROUP_CASES)
def test_live_group_case(live_groups,case_name):assert_case(live_groups,case_name)


@pytest.mark.parametrize('case_name',COMMENT_CASES)
def test_live_comment_case(live_comments,case_name):assert_case(live_comments,case_name)


def test_live_group_cleanup(live_groups):
    assert all(x['status'] in ('dissolved-read-only','uploaded-retained') for x in live_groups.report['resources'])


def test_live_comment_cleanup(live_comments):
    assert not live_comments.report.get('reaction_cleanup_errors')
    assert all(x['status']=='deleted' for x in live_comments.report['resources'])
