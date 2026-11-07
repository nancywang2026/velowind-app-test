"""Ordered Postman flow; every operation remains independently reusable."""
import time
import allure
import uuid
from contextlib import contextmanager
from . import checks
from .console import log
from .auth import login
from .config import validate_config
from .conversations import Conversations
from .follows import follow
from .history import History
from .http import ApiError, HttpClient
from .messages import Messages
from .sharing import Sharing


def new_report():
    return {"run_id": str(uuid.uuid4()), "status": "not_started", "start": int(time.time() * 1000), "steps": [], "requests": [],
            "message_ids": [], "cleanup": "not_needed", "device_validation": "not_run"}


@contextmanager
def step(report, name):
    record = {"name": name, "status": "running", "start": int(time.time() * 1000), "request_start": len(report["requests"])}
    report["steps"].append(record)
    started = time.monotonic()
    log("STEP", f"开始 {name}")
    try:
        with allure.step(name):
            yield
        record["status"] = "passed"
    except Exception as exc:
        record["status"] = "failed"
        # Errors produced here deliberately exclude response payloads and credentials.
        record["error_type"] = type(exc).__name__
        log("ERROR", str(exc) if isinstance(exc, (AssertionError, ApiError)) else type(exc).__name__)
        if isinstance(exc, AssertionError):
            record["error"] = str(exc)
        raise
    finally:
        record["request_stop"] = len(report["requests"])
        record["stop"] = int(time.time() * 1000)
        record["duration_seconds"] = round(time.monotonic() - started, 3)
        log("PASS" if record["status"] == "passed" else "FAIL",
            f"{name} ({record['duration_seconds']:.2f}s)")


def run(config, report=None, http=None):
    report = report if report is not None else new_report()
    report["status"] = "running"
    try:
        validate_config(config)
        execution = config["execution"]
        http = http or HttpClient(config["base_url"], execution["http_timeout_seconds"],
                                  execution["request_interval_seconds"], report["requests"])
        run_id = report["run_id"]
        with step(report, "01 登录 A/B/C，校验身份互异"):
            users = {role: login(http, config["accounts"][role]) for role in ("a", "b", "c")}
            checks.require(len({u.user_id for u in users.values()}) == 3, "Login identities must differ")
        a, b, c = (users[role] for role in ("a", "b", "c"))
        ac, bc = Conversations(http, a), Conversations(http, b)
        am = Messages(http, a, execution.get("send_interval_seconds", 0))
        with step(report, "02 A关注B"):
            report["cleanup"] = "not_performed; follow/conversation state and messages may remain"
            follow(http, a, b.user_id)
        with step(report, "03 B未读基线"):
            baseline_item = checks.peer(bc.list(), a.user_id, required=False)
            baseline = checks.unread(baseline_item)
            report["initial_unread_b"] = baseline
            log("DATA", f"B 初始未读={baseline}，预期基线={config['expected']['baseline_unread_b']}")
            if baseline and config.get("preparation", {}).get("mark_b_history_read", False):
                with allure.step("准备B与A会话：历史标记已读并复查"):
                    conversation_id = checks.identifier(baseline_item.get("conversationId"), "conversationId")
                    log("PREPARE", "将B与A会话历史标记已读，随后复查")
                    prepared = bc.mark_read(a.user_id, conversation_id)
                    report["preparation"] = {"mark_b_history_read": True,
                                             "marked_read_count": prepared["markedReadCount"]}
                    baseline = checks.unread(checks.peer(bc.list(), a.user_id))
            report["baseline_unread_b"] = baseline
            log("DATA", f"B 验证基线={baseline}")
            checks.require(baseline == config["expected"]["baseline_unread_b"],
                           f"Unread baseline mismatch: expected={config['expected']['baseline_unread_b']}, actual={baseline}; "
                           "enable preparation.mark_b_history_read or use clean accounts (no messages sent this run)")

        def batch(recipient, data_key):
            spec = config["messages"][data_key]
            results = []
            for index in range(1, spec["count"] + 1):
                content = spec["template"].format(run_id=run_id, index=index, count=spec["count"])
                log("SEND", f"A→{data_key.removeprefix('to_').upper()} 文本 {index}/{spec['count']}")
                message = am.send_text(recipient.user_id, content)
                checks.require(message["messageId"] not in report["message_ids"], "Reused messageId")
                report["message_ids"].append(message["messageId"])
                results.append(message)
            return results

        with step(report, "04 A向B发送文本"):
            sent_b = batch(b, "to_b")
        with step(report, "05 B列表未读总数及增量"):
            actual = checks.unread(checks.peer(bc.list(), a.user_id))
            report.update(actual_unread_b=actual, unread_delta_b=actual - baseline)
            log("DATA", f"B 实际未读={actual}，新增={actual - baseline}，预期总数={config['expected']['unread_b']}")
            checks.require(actual == config["expected"]["unread_b"], "Unread total mismatch")
            checks.require(actual - baseline == config["expected"]["unread_delta_b"], "Unread delta mismatch")
        with step(report, "06 A向C发送文本"):
            sent_c = batch(c, "to_c")
        with step(report, "07 A置顶C并验证列表排序"):
            ac.pin(c.user_id)
            checks.pinned(ac.list(), c.user_id)
        with step(report, "08 A隐藏B并验证双方视角"):
            ac.hide(b.user_id)
            checks.require(checks.peer(ac.list(), b.user_id, required=False) is None,
                           "Hidden peer remains visible in A list")
            checks.require(checks.unread(checks.peer(bc.list(), a.user_id)) == actual,
                           "A hide changed B conversation unread")
        sharing = Sharing(am)
        with step(report, "09 A分享笔记给B"):
            post = sharing.post(b.user_id, config["resources"]["post_id"],
                                config["messages"]["post_share"].format(run_id=run_id))
            report["message_ids"].append(post["messageId"])
        with step(report, "10 A分享活动给C及最终会话列表"):
            activity = sharing.activity(c.user_id, config["resources"]["activity_id"],
                                        config["messages"]["activity_share"].format(run_id=run_id))
            report["message_ids"].append(activity["messageId"])
            checks.require(len(set(report["message_ids"])) == len(report["message_ids"]), "Reused messageId")
            items = ac.list()
            checks.pinned(items, c.user_id)
            checks.card(checks.peer(items, c.user_id).get("latestMessage") or {},
                        "ACTIVITY", config["resources"]["activity_id"])
            # Hidden conversation visibility after a new outgoing share is not asserted.
            report["a_b_visible_after_share"] = checks.peer(items, b.user_id, required=False) is not None
        for role, recipient, sent, shared, kind, resource in (
            ("B", b, sent_b, post, "POST", "post_id"),
            ("C", c, sent_c, activity, "ACTIVITY", "activity_id"),
        ):
            with step(report, f"11 {role}读取文本与分享卡片"):
                expected = sent + [shared]
                history = History(http, recipient, execution["page_size"], execution["max_pages"])
                found = history.find(a.user_id, [m["messageId"] for m in expected])
                for original in expected:
                    received = found[str(original["messageId"])]
                    checks.message(received, a.user_id, recipient.user_id, original["content"],
                                   original["clientMessageId"], original["messageId"], recipient_view=True)
                    checks.require(received.get("conversationId") == original["conversationId"],
                                   "Message arrived in wrong conversation")
                checks.card(found[str(shared["messageId"])], kind, config["resources"][resource])
        report["status"] = "passed"
        return report
    except BaseException:
        report["status"] = "failed"
        raise
