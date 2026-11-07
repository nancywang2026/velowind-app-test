"""Executable journeys aligned to the approved CSV; no October-excluded cases.

Prepared values identify current-run data. Observed values must be obtained by
the corresponding real API/UI operation; absence blocks, never passes.
"""
from __future__ import annotations
from dataclasses import dataclass
from .core import Blocked, require
from .program import check, lookup


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    variants: tuple
    operations: tuple
    assertions: tuple
    conditional: str = ""


def eq(actual, expected): return (actual, "eq", expected)


NOTIFICATION_CHECKS = (
    eq("notification.biz_id", "$prepare.biz_id"),
    eq("notification.recipient_id", "$prepare.recipient_id"),
    eq("notification.event_type", "$prepare.event_type"),
    eq("notification.new_event_count", 1),
    eq("notification.detail_matches", True),
    eq("notification.return_possible", True),
    eq("notification.reentry_matches", True),
)


def notice(case_id, title, event, variants=("default",), condition=""):
    return Case(case_id, title, variants, (event, "notification"), NOTIFICATION_CHECKS,
                conditional=condition)


CASES = (
    notice("MSG-001", "发布笔记后系统通知", "publish_note", ("photo", "album_video", "record_video")),
    notice("MSG-001-R", "笔记审核拒绝通知", "reject_note"),
    notice("MSG-032", "发布活动后系统通知", "publish_activity"),
    notice("MSG-002", "活动报名成功通知", "enroll_activity", ("free_auto", "test_paid")),
    notice("MSG-003", "报名被拒绝通知", "reject_enrollment"),
    notice("MSG-004", "取消报名通知", "cancel_enrollment", ("self", "leader")),
    notice("MSG-005", "活动退款成功通知", "refund_enrollment", condition="test_payment_refund"),
    notice("MSG-005-RENTAL", "租车退款成功通知", "refund_rental", condition="test_payment_refund"),
    Case("MSG-006", "互动分类完整性", ("default",), ("interaction_events", "categories"), (
        ("categories.all_ids", "same_set", "$prepare.event_ids"),
        ("categories.like_favorite_ids", "same_set", "$prepare.like_favorite_ids"),
        ("categories.follow_ids", "same_set", "$prepare.follow_ids"),
        ("categories.comment_mention_ids", "same_set", "$prepare.comment_mention_ids"),
        eq("categories.duplicates", 0))),
    notice("MSG-007", "评论点赞收藏后通知", "comment_reaction", ("like", "favorite")),
    Case("MSG-008", "查看笔记关注作者后通知及回关聊天", ("default",),
         ("browse_follow", "notification", "follow_back_chat"), NOTIFICATION_CHECKS + (
             eq("follow_back_chat.mutual", True), eq("follow_back_chat.correct_peer", True),
             eq("follow_back_chat.recipient_received", True))),
    Case("MSG-009", "评论实际@、活动评论及回复后通知", ("mention", "activity_comment", "reply"),
         ("publish_comment", "notification", "comment_location"), NOTIFICATION_CHECKS + (
             eq("comment_location.comment_id", "$prepare.comment_id"),
             eq("comment_location.target_id", "$prepare.target_id"),
             eq("comment_location.content", "$prepare.content"),
             eq("comment_location.time_visible", True), eq("comment_location.original_relation_matches", True))),
    Case("MSG-010", "私信文字双向收发及空格拦截", ("default",),
         ("private_text", "private_delivery"), (
             eq("private_text.whitespace_added", 0), eq("private_delivery.outbound_count", 1),
             eq("private_delivery.reply_count", 1), eq("private_delivery.content", "$prepare.content"),
             eq("private_delivery.receiver_id", "$prepare.receiver_id"),
             eq("private_delivery.unrelated_count", 0), eq("private_delivery.reentry_persisted", True))),
    Case("MSG-011", "私信纯图片收发及重进", ("default",), ("private_image", "image_delivery"), (
             eq("image_delivery.sender_matches", True), eq("image_delivery.recipient_matches", True),
             eq("image_delivery.full_image_loaded", True), eq("image_delivery.reentry_loaded", True),
             eq("image_delivery.expected_image_digest", "$prepare.image_digest"))),
    Case("MSG-012", "多条私信最新定位、历史翻页与时间", ("text", "image"),
         ("private_history", "latest_position", "history_during_incoming"), (
             eq("latest_position.enter_latest_id", "$prepare.latest_id"),
             eq("latest_position.reenter_latest_id", "$prepare.latest_id"),
             eq("latest_position.bottom_follows_latest", True), eq("latest_position.unobscured", True),
             eq("history_during_incoming.anchor_before", "$prepare.history_anchor"),
             eq("history_during_incoming.anchor_after", "$prepare.history_anchor"),
             eq("history_during_incoming.duplicates", 0), eq("history_during_incoming.missing", 0),
             eq("history_during_incoming.time_matches", True))),
    Case("MSG-013", "私信逐条未读已读图标及会话计数", ("text", "image"),
         ("private_receipts", "read_by_recipient", "send_another", "receipt_reentry"), (
             eq("private_receipts.before_state", "unread"), eq("private_receipts.list_only_marks_read", False),
             eq("read_by_recipient.sender_icon", "read"), eq("read_by_recipient.conversation_unread", 0),
             eq("read_by_recipient.other_unread", "$prepare.other_unread"),
             eq("send_another.old_message_state", "read"), eq("send_another.new_message_state", "unread"),
             eq("receipt_reentry.new_message_after_read", "read"), eq("receipt_reentry.persisted", True))),
    Case("MSG-014", "清空私信与双方历史隔离", ("default",),
         ("clear_private", "private_clear_reentry"), (
             eq("private_clear_reentry.cleared_old_count", 0), eq("private_clear_reentry.peer_history_matches", True),
             eq("private_clear_reentry.new_received", True), eq("private_clear_reentry.restart_cleared", True))),
    Case("MSG-015", "笔记活动卡片分享到私信群聊", ("post_private", "activity_private", "post_group", "activity_group"),
         ("share_content", "shared_card"), (
             eq("shared_card.biz_id", "$prepare.biz_id"), eq("shared_card.count", 1),
             eq("shared_card.recipient_received", True), eq("shared_card.detail_id", "$prepare.biz_id"),
             eq("shared_card.return_possible", True), eq("shared_card.reentry_usable", True))),
    Case("MSG-016", "私信群聊发送未知结果及防重", ("private_before_send", "private_after_commit", "group_before_send", "group_after_commit"),
         ("inject_send_failure", "send_recovery"), (
             eq("send_recovery.displayed_state", "$prepare.expected_send_state"),
             eq("send_recovery.occurrences", "$prepare.expected_occurrences"),
             eq("send_recovery.automatic_resend", False), eq("send_recovery.failure_rule_removed", True)), "fault_injection"),
    Case("MSG-017", "活动上架建群与报名自动入群", ("default",),
         ("publish_activity", "enroll_activity", "activity_group"), (
             eq("activity_group.group_count", 1), eq("activity_group.activity_id", "$prepare.activity_id"),
             eq("activity_group.enrolled_user_is_member", True), eq("activity_group.name_matches", True),
             eq("activity_group.member_count_matches", True), eq("activity_group.detail_activity_id", "$prepare.activity_id"))),
    Case("MSG-018", "建群表单与真实创建结果", ("default",), ("create_group", "created_group"), (
             eq("created_group.empty_created_count", 0), eq("created_group.new_count", 1),
             eq("created_group.name", "$prepare.name"), eq("created_group.description", "$prepare.description"),
             eq("created_group.owner_id", "$prepare.owner_id"), eq("created_group.ui_api_consistent", True),
             eq("created_group.reentry_exists", True))),
    Case("MSG-019", "邀请好友直接入群及接受邀请", ("direct", "accept"), ("invite_group", "invitation_result"), (
             eq("invitation_result.selected_ids", "$prepare.invitee_ids"),
             eq("invitation_result.actual_member_ids", "$prepare.expected_member_ids"),
             eq("invitation_result.private_invitation_matches", "$prepare.invitation_expected"),
             eq("invitation_result.accept_twice_duplicates", 0), eq("invitation_result.count_matches", True))),
    Case("MSG-020", "群成员数随加入退出同步", ("default",), ("join_leave", "member_counts"), (
             eq("member_counts.joined_count", "$prepare.joined_count"),
             eq("member_counts.left_count", "$prepare.initial_count"), eq("member_counts.all_views_match", True),
             eq("member_counts.actual_member_ids", "$prepare.initial_member_ids"))),
    Case("MSG-021", "群置顶取消持久化", ("default",), ("pin_group", "unpin_group"), (
             eq("pin_group.pinned", True), eq("pin_group.first_id", "$prepare.group_id"),
             eq("pin_group.reentry_pinned", True), eq("unpin_group.pinned", False),
             eq("unpin_group.reentry_pinned", False), eq("unpin_group.private_ids", "$prepare.private_ids"))),
    Case("MSG-022", "群免打扰红点与恢复计数", ("default",), ("mute_incoming", "unmute_incoming"), (
             eq("mute_incoming.received", True), eq("mute_incoming.indicator", "dot"),
             eq("mute_incoming.read_clears", True), eq("unmute_incoming.indicator", "count"),
             eq("unmute_incoming.persisted", True))),
    Case("MSG-023", "群清空记录及其他成员隔离", ("default",), ("clear_group", "group_clear_reentry"), (
             eq("group_clear_reentry.old_count", 0), eq("group_clear_reentry.peer_history_matches", True),
             eq("group_clear_reentry.new_received", True), eq("group_clear_reentry.restart_cleared", True))),
    Case("MSG-024", "群历史连续分页及新成员范围", ("existing_member", "new_member"), ("group_history",), (
             eq("group_history.duplicates", 0), eq("group_history.missing", 0),
             ("group_history.ids", "same_set", "$prepare.visible_message_ids")), "history_visibility_rule"),
    Case("MSG-025", "群文字图片双向收发", ("text", "image"), ("group_send", "group_delivery"), (
             eq("group_delivery.message_ids", "$prepare.message_ids"), eq("group_delivery.correct_senders", True),
             eq("group_delivery.correct_contents", True), eq("group_delivery.all_recipients_received", True),
             eq("group_delivery.unrelated_count", 0), eq("group_delivery.reentry_media_usable", True))),
    Case("MSG-026", "群成员跨页搜索和改名", ("default",), ("search_members", "rename_search"), (
             eq("search_members.found_user_id", "$prepare.target_user_id"), eq("search_members.nonmember_found", False),
             eq("search_members.missing_keyword_empty", True), eq("rename_search.new_name_found", True))),
    Case("MSG-027", "群公告群主编辑与成员权限", ("default",), ("edit_announcement", "announcement_member"), (
             eq("announcement_member.content", "$prepare.announcement"), eq("announcement_member.reentry_matches", True),
             eq("announcement_member.member_can_edit", False))),
    Case("MSG-028", "移除成员或退出后的权限", ("remove", "leave"), ("remove_or_leave", "former_member"), (
             eq("former_member.in_member_ids", False), eq("former_member.can_send", False),
             eq("former_member.receives_new", False), eq("former_member.member_count_matches", True),
             eq("former_member.history_matches_rule", True)), "history_visibility_rule"),
    Case("MSG-029", "群资料及群主解散权限", ("default",), ("edit_group", "member_dissolve", "owner_dissolve"), (
             eq("edit_group.name", "$prepare.name"), eq("edit_group.description", "$prepare.description"),
             eq("edit_group.member_sees_update", True), eq("member_dissolve.allowed", False),
             eq("member_dissolve.group_still_exists", True), eq("owner_dissolve.group_exists", False),
             eq("owner_dissolve.former_member_can_send", False))),
    Case("MSG-030", "私信接收权限矩阵", ("all", "followers", "following", "mutual", "closed"),
         ("set_private_scope", "private_scope_result"), (
             ("private_scope_result.allowed_ids", "same_set", "$prepare.allowed_ids"),
             ("private_scope_result.rejected_ids", "same_set", "$prepare.rejected_ids"),
             eq("private_scope_result.actual_received_ids", "$prepare.allowed_ids"),
             eq("private_scope_result.persisted", True)), "october_privacy_scope"),
    Case("MSG-031", "入群接收偏好与邀请约束", ("direct", "reject", "verify"),
         ("set_group_scope", "group_scope_result"), (
             eq("group_scope_result.member_ids", "$prepare.member_ids"),
             eq("group_scope_result.invitation_received", "$prepare.invitation_expected"),
             eq("group_scope_result.persisted", True)), "october_privacy_scope"),
)


def run_case(case, variant, program, *, capabilities=()):
    if variant not in case.variants: raise ValueError("Unknown journey variant")
    if case.conditional and case.conditional not in capabilities:
        raise Blocked(f"{case.id}: prerequisite {case.conditional}")
    names = ("prepare." + case.id, *case.operations, "cleanup." + case.id)
    program.preflight(names)  # Entire case, including cleanup, before any mutation.
    prepared = None
    results = {}
    primary = None
    try:
        # Register cleanup scope in context before prepare (unknown outcome included).
        program.context.update(case_id=case.id, variant=variant)
        prepared = program.run(names[0], variant=variant)
        program.context["prepare"] = prepared
        for operation in case.operations:
            results[operation] = program.run(operation, variant=variant, prepared=prepared)
        facts = {**results, "prepare": prepared}
        for path, operator, expected in case.assertions:
            if isinstance(expected, str) and expected.startswith("$"):
                expected = lookup(facts, expected[1:])
            check(lookup(facts, path), expected, operator)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        try:
            cleaned = program.run("cleanup." + case.id, variant=variant, prepared=prepared or {})
            require(cleaned.get("remaining_ids") == [], "cleanup-pending: current-run resources remain")
            require(cleaned.get("restored") is True, "cleanup-pending: account baseline not restored")
        except Exception as exc:
            program.report.append({"case_id": case.id, "status": "cleanup-pending", "error": type(exc).__name__})
            if primary is None: raise
            # Preserve both outcomes; pytest fixture will fail teardown separately.
            program.context.setdefault("cleanup_errors", []).append(type(exc).__name__)
    return results
