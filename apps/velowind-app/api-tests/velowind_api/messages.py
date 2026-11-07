import uuid
import time
import allure
from . import checks
from .console import log
from .conversations import peer_path


class Messages:
    def __init__(self, http, actor, send_interval_seconds=0):
        self.http, self.actor = http, actor
        self.send_interval_seconds = send_interval_seconds
        self.last_send_finished = None

    def send_text(self, peer_id, content, *, context=None, client_id=None):
        if self.last_send_finished is not None:
            remaining = self.send_interval_seconds - (time.monotonic() - self.last_send_finished)
            if remaining > 0:
                log("WAIT", f"遵守发送间隔，等待 {remaining:.1f}s")
                with allure.step(f"发送间隔等待 {remaining:.1f} 秒"):
                    time.sleep(remaining)
        client_id = client_id or str(uuid.uuid4())
        payload = {"contentType": "TEXT", "content": content, "clientMessageId": client_id}
        if context is not None:
            payload["context"] = context
        data = self.http.request("POST", peer_path(peer_id) + "/messages", token=self.actor.token,
                                 body=payload, request_id=client_id)
        self.last_send_finished = time.monotonic()
        checks.message(data, self.actor.user_id, peer_id, content, client_id)
        return data
