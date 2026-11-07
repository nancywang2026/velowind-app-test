from .checks import identifier, require
from .conversations import peer_path


class History:
    def __init__(self, http, actor, page_size=50, max_pages=20):
        self.http, self.actor = http, actor
        self.page_size, self.max_pages = page_size, max_pages

    def find(self, peer_id, expected_ids):
        """Read latest snapshot then forward pages. Never calls read/read-all.

        Backend has no backwards cursor: a missing old message is a failure,
        not proof that complete historical storage has been traversed.
        A recovery page replaces the prior partial snapshot.
        """
        expected_ids = {str(x) for x in expected_ids}
        found, seen_cursors, cursor, recoveries = {}, set(), None, 0
        for _ in range(self.max_pages):
            params = {"pageSize": self.page_size}
            if cursor:
                params["afterMessageId"] = cursor
            page = self.http.request("GET", peer_path(peer_id) + "/messages",
                                     token=self.actor.token, params=params)
            messages = page.get("messages")
            require(isinstance(messages, list) and all(isinstance(x, dict) for x in messages),
                    "Invalid history messages")
            require(type(page.get("hasMore")) is bool, "Invalid history hasMore")
            require(type(page.get("resyncRequired")) is bool, "Invalid history resyncRequired")
            if page["resyncRequired"]:
                recoveries += 1
                require(recoveries <= 1, "History repeatedly requires resync")
                found, seen_cursors = {}, set()
            for item in messages:
                key = identifier(item.get("messageId"), "history messageId")
                if key in expected_ids:
                    require(key not in found, "Duplicate target message in history")
                    found[key] = item
            if not page["hasMore"]:
                require(expected_ids <= found.keys(), "Target messages missing from available history window")
                return found
            next_cursor = page.get("latestReturnedMessageId")
            require(isinstance(next_cursor, str) and bool(next_cursor), "Missing history cursor")
            require(next_cursor not in seen_cursors and next_cursor != cursor, "History cursor did not advance")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        raise AssertionError("History page limit exceeded; result incomplete")
