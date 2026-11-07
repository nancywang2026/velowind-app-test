"""Local HTTP contract harness; does not claim deployed backend validation."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager
from copy import deepcopy
import pytest
from velowind_api.scenario import new_report, run


@contextmanager
def backend(config, defect=None):
    messages, calls, pins, hidden = [], [], set(), set()
    history_unread = [26 if defect in ("baseline", "read_not_effective", "read_wrong_conversation") else 0]
    phones = {v["phone"]: k for k, v in config["accounts"].items()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.handle_api()

        def do_POST(self):
            self.handle_api()

        def handle_api(self):
            actor = self.headers.get("Authorization", "").removeprefix("Bearer token-")
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"]))) if int(self.headers.get("Content-Length", 0)) else None
            route = self.path.split("?")[0]
            calls.append((self.command, route, actor, body, self.headers.get("X-Request-Id")))
            data = {}
            if route.endswith("/auth/login/phone/password"):
                user = phones[body["phone"]]
                data = {"userId": user, "accessToken": "token-" + user}
            elif route.endswith("/user-follows"):
                data = {"targetUserId": body["targetUserId"], "following": True}
            elif route.endswith("/private-conversations"):
                peers = {m["receiverUserId"] if m["senderUserId"] == actor else m["senderUserId"]
                         for m in messages if actor in (m["senderUserId"], m["receiverUserId"])}
                items = []
                for peer in sorted(peers):
                    if (actor, peer) in hidden and defect != "hide":
                        continue
                    pair = [m for m in messages if {m["senderUserId"], m["receiverUserId"]} == {actor, peer}]
                    count = sum(m["receiverUserId"] == actor for m in pair)
                    if defect == "unread" and actor == "b":
                        count += 1
                    items.append({"peerUserId": peer, "unreadCount": count,
                                  "pinned": (actor, peer) in pins and defect != "pin",
                                  "latestMessage": pair[-1]})
                if actor == "b" and not messages and defect in ("baseline", "read_not_effective", "read_wrong_conversation"):
                    items = [{"peerUserId": "a", "conversationId": "a-b", "unreadCount": history_unread[0], "pinned": False}]
                data = {"items": sorted(items, key=lambda x: not x["pinned"])}
            else:
                peer = route.split("/")[-2]
                action = route.split("/")[-1]
                if action == "read":
                    count = history_unread[0]
                    if defect != "read_not_effective":
                        history_unread[0] = 0
                    data = {"conversationId": "other" if defect == "read_wrong_conversation" else "a-b",
                            "markedReadCount": count, "conversationUnreadCount": 0}
                elif action in ("pin", "hide"):
                    (pins if action == "pin" else hidden).add((actor, peer))
                    data = {"peerUserId": peer, "pinned": action == "pin", "hidden": action == "hide"}
                elif self.command == "POST" and action == "messages":
                    data = {"messageId": str(len(messages) + 1), "conversationId": "-".join(sorted([actor, peer])),
                            "senderUserId": actor, "receiverUserId": peer, "contextCard": body.get("context"),
                            "content": body["content"], "contentType": body["contentType"],
                            "clientMessageId": body["clientMessageId"]}
                    if defect == "card" and body.get("context"):
                        data["contextCard"] = {**body["context"], "bizId": "wrong"}
                    messages.append(deepcopy(data))
                elif self.command == "GET" and action == "messages":
                    selected = deepcopy([m for m in messages if {m["senderUserId"], m["receiverUserId"]} == {actor, peer}])
                    for message in selected:
                        message["direction"] = "INBOUND" if message["receiverUserId"] == actor else "OUTBOUND"
                        if message["direction"] == "INBOUND":
                            message["clientMessageId"] = None
                    if defect == "missing_text":
                        selected = selected[1:]
                    if defect == "receiver":
                        selected[-1]["receiverUserId"] = "someone-else"
                    data = {"messages": selected, "hasMore": False, "resyncRequired": False,
                            "latestReturnedMessageId": selected[-1]["messageId"] if selected else None}
                else:
                    raise AssertionError("Unexpected API route")
            payload = json.dumps({"code": 0, "data": data}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    config["base_url"] = f"http://127.0.0.1:{server.server_port}"
    try:
        yield calls
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_full_flow_through_http(config):
    with backend(config) as calls:
        report = run(config)
    assert report["status"] == "passed"
    assert len(report["message_ids"]) == 10
    assert report["actual_unread_b"] == 3
    assert len(report["steps"]) == 12
    sent = [c for c in calls if c[0] == "POST" and c[1].endswith("/messages")]
    assert len({c[4] for c in sent}) == 10
    assert all(c[3]["clientMessageId"] == c[4] for c in sent)
    activity = sent[-1][3]["context"]
    assert "bizType" not in activity
    assert sent[-2][3]["context"]["bizType"] == "POST"
    assert not any(c[1].endswith(("/read", "/read-all", "/clear")) for c in calls)
    first_history = next(i for i, c in enumerate(calls) if c[0] == "GET" and c[1].endswith("/messages"))
    last_send = max(i for i, c in enumerate(calls) if c in sent)
    assert first_history > last_send
    serialized = json.dumps(report)
    assert "test-password" not in serialized and "token-" not in serialized
    assert report["cleanup"].startswith("not_performed")


@pytest.mark.parametrize("defect,step_prefix", [("baseline", "03"), ("unread", "05"), ("pin", "07"),
                                                ("hide", "08"), ("card", "09"),
                                                ("missing_text", "11"), ("receiver", "11")])
def test_business_failures_stop_flow(config, defect, step_prefix):
    report = new_report()
    with backend(config, defect) as calls:
        with pytest.raises(AssertionError):
            run(config, report)
    assert report["status"] == "failed"
    assert report["steps"][-1]["name"].startswith(step_prefix)
    assert report["steps"][-1]["status"] == "failed"
    if defect == "baseline":
        assert not any(c[0] == "POST" and c[1].endswith("/messages") for c in calls)


def test_coverage_matches_exported_postman_requests(config):
    from collections import Counter
    from pathlib import Path
    contract = json.loads((Path(__file__).resolve().parents[1] / "data/postman-contract.json").read_text())
    with backend(config) as calls:
        run(config)
    variables = {f"user_id_{role}": role for role in config["accounts"]}
    expected = []
    for request in contract["requests"]:
        path = request["url"].replace("{{base_url}}", "").split("?")[0]
        for name, value in variables.items():
            path = path.replace("{{" + name + "}}", value)
        actor = request["actor"]
        actor = "" if actor == "anonymous" else actor.split("access_token_")[1][0]
        expected.append((request["method"], path, actor))
    # Additional read verifies A's hide does not affect B's view/unread.
    expected.append(("GET", "/api/v1/mobile/message-center/private-conversations", "b"))
    assert len(contract["requests"]) == 23
    assert Counter((c[0], c[1], c[2]) for c in calls) == Counter(expected)


@pytest.mark.parametrize("defect,expected_code,expected_status", [(None, 0, "passed"), ("unread", 1, "failed")])
def test_cli_exit_and_report(config, tmp_path, monkeypatch, defect, expected_code, expected_status):
    import sys
    from velowind_api.__main__ import main
    data, report = tmp_path / "data.json", tmp_path / "report.json"
    with backend(config, defect):
        data.write_text(json.dumps(config))
        monkeypatch.setattr(sys, "argv", ["velowind_api", "--data", str(data), "--report", str(report), "--alluredir", str(tmp_path / "allure-results")])
        assert main() == expected_code
    assert json.loads(report.read_text())["status"] == expected_status


def test_prepare_existing_unread_then_verify_three(config):
    config['preparation'] = {'mark_b_history_read': True}
    with backend(config, 'baseline') as calls:
        report = run(config)
    assert report['status'] == 'passed'
    assert report['initial_unread_b'] == 26
    assert report['baseline_unread_b'] == 0
    assert report['actual_unread_b'] == 3
    read_calls = [i for i,c in enumerate(calls) if c[1].endswith('/read')]
    assert len(read_calls) == 1
    assert calls[read_calls[0]][2] == 'b'
    assert calls[read_calls[0]][1].endswith('/a/read')
    assert read_calls[0] < next(i for i,c in enumerate(calls) if c[0] == 'POST' and c[1].endswith('/messages'))


@pytest.mark.parametrize('defect', ['read_not_effective', 'read_wrong_conversation'])
def test_failed_preparation_stops_before_sending(config, defect):
    config['preparation'] = {'mark_b_history_read': True}
    with backend(config, defect) as calls:
        with pytest.raises(AssertionError):
            run(config)
    assert not any(c[0] == 'POST' and c[1].endswith('/messages') for c in calls)


def test_clean_baseline_never_calls_read(config):
    config['preparation'] = {'mark_b_history_read': True}
    with backend(config) as calls:
        run(config)
    assert not any(c[1].endswith('/read') for c in calls)


@pytest.mark.parametrize('defect,expected_code', [(None,0),('unread',1)])
def test_auto_report_opens_after_success_and_failure(config,tmp_path,monkeypatch,defect,expected_code):
    import sys
    from unittest.mock import Mock
    from velowind_api import __main__ as cli
    data, report = tmp_path/'data.json', tmp_path/'report.json'
    opened = Mock(return_value=True)
    monkeypatch.setattr(cli,'open_report',opened)
    with backend(config,defect):
        data.write_text(json.dumps(config))
        monkeypatch.setattr(sys,'argv',['velowind_api','--data',str(data),'--report',str(report),
                                     '--alluredir',str(tmp_path/'allure-results'),'--open-report'])
        assert cli.main() == expected_code
    opened.assert_called_once_with(str(tmp_path/'allure-results'),str(tmp_path/'allure-report'))
