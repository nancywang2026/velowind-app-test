from urllib.parse import quote
from .checks import require

ROOT = "/api/v1/mobile/message-center/private-conversations"


def peer_path(peer_id):
    return ROOT + "/" + quote(str(peer_id), safe="")


class Conversations:
    def __init__(self, http, actor):
        self.http, self.actor = http, actor

    def list(self):
        data = self.http.request("GET", ROOT, token=self.actor.token)
        items = data.get("items")
        require(isinstance(items, list) and all(isinstance(x, dict) for x in items),
                "Invalid conversation items")
        return items

    def _change(self, peer_id, action, field):
        data = self.http.request("POST", peer_path(peer_id) + "/" + action, token=self.actor.token)
        require(str(data.get("peerUserId")) == str(peer_id), "Conversation state peer mismatch")
        require(data.get(field) is True, f"Conversation {field} did not become true")
        return data

    def pin(self, peer_id):
        return self._change(peer_id, "pin", "pinned")

    def hide(self, peer_id):
        return self._change(peer_id, "hide", "hidden")

    def mark_read(self, peer_id, conversation_id):
        """Prepare only this actor/peer conversation; never deletes messages."""
        data = self.http.request("POST", peer_path(peer_id) + "/read", token=self.actor.token)
        require(str(data.get("conversationId")) == str(conversation_id), "Read response conversation mismatch")
        require(type(data.get("markedReadCount")) is int and data["markedReadCount"] >= 0,
                "Invalid markedReadCount")
        require(type(data.get("conversationUnreadCount")) is int and data["conversationUnreadCount"] == 0,
                "Mark-read did not reset conversation unread to zero")
        return data
