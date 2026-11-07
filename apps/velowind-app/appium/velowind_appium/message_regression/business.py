from __future__ import annotations

import uuid
from .core import Blocked, identifier, require, segment, wait

ROOT = "/api/v1/mobile/message-center"


class Messages:
    def __init__(self, api): self.api = api

    def notifications(self, actor, category=None, types=None):
        params = {}
        if category: params["category"] = category
        if types: params["notificationTypes"] = types
        return self.api.pages(actor, ROOT + "/system-messages", params=params, id_key="inboxId")

    def notification_after(self, actor, baseline, business_id, notification_type, *, category=None):
        require(bool(notification_type), "Explicit notification type required")
        def matching():
            return [row for row in self.notifications(actor, category)
                    if str(row.get("inboxId")) not in baseline
                    and row.get("notificationType") == notification_type
                    and str((row.get("action") or {}).get("bizId", row.get("bizId"))) == str(business_id)]
        rows = wait(matching, bool)
        require(len(rows) == 1, "Duplicate notifications for the current event")
        row = rows[0]
        detail = self.api.request(actor, "GET", ROOT + "/system-messages/" + segment(row["inboxId"]))
        require(str((detail.get("action") or {}).get("bizId", detail.get("bizId"))) == str(business_id),
                "Notification detail points to another business object")
        return detail

    def conversations(self, actor):
        data = self.api.request(actor, "GET", ROOT + "/private-conversations")
        require(isinstance(data, dict) and isinstance(data.get("items"), list), "Invalid private conversation list")
        return data["items"]

    def conversation(self, actor, peer):
        rows = [x for x in self.conversations(actor) if str(x.get("peerUserId")) == peer.user_id]
        require(len(rows) <= 1, "Duplicate peer conversation")
        return rows[0] if rows else None

    def unread(self, actor, peer):
        row = self.conversation(actor, peer)
        value = row.get("unreadCount") if row else 0
        require(type(value) is int and value >= 0, "Invalid unreadCount")
        return value

    def send(self, actor, recipient, text, *, group=False, image_ids=None, context=None, client_id=None):
        client_id = client_id or str(uuid.uuid4())
        path = ROOT + ("/chatrooms/" if group else "/private-conversations/") + segment(recipient) + "/messages"
        body = {"contentType": "IMAGE" if image_ids else "TEXT", "content": text, "clientMessageId": client_id}
        if image_ids: body["imageAssetIds"] = list(image_ids)
        if context: body["context"] = context
        data = self.api.request(actor, "POST", path, body=body,request_id=client_id)
        require(isinstance(data, dict), "Missing sent message response")
        if image_ids:
            # An accepted image request may still be processing. Never resend it.
            result_path = path.rsplit("/messages", 1)[0] + "/message-send-results/" + segment(client_id)
            result = wait(lambda: self.api.request(actor, "GET", result_path,
                          params=None if group else {"sendEntry": "CONVERSATION"}),
                          lambda x: x.get("status") in {"SENT", "FAILED", "UNKNOWN"}, timeout=60)
            if result.get("status") == "UNKNOWN":
                raise Blocked("Image send result unconfirmed; automatic resend prohibited")
            require(result.get("status") == "SENT", "Image send failed: SEND_FAILED")
            require(result.get("contentAvailable") is True and isinstance(result.get("message"), dict),
                    "Sent image message is not visible to sender")
            data = result["message"]
        identifier(data.get("messageId"))
        require(str(data.get("senderUserId")) == actor.user_id, "Wrong message sender")
        if image_ids and not text:
            require(data.get("content") in (None, ""), "Unexpected caption on captionless image")
        else:
            require(data.get("content") == text, "Sent message body mismatch")
        require(data.get("clientMessageId") == client_id, "Send acknowledgement client ID mismatch")
        return data

    def history(self, actor, recipient, *, group=False, expected_ids=(), page_size=50, max_pages=40, direction="newer"):
        """Use actual before/after anchors; older history is available in current API."""
        require(direction in {"older","newer"},"Invalid history direction")
        path = ROOT + ("/chatrooms/" if group else "/private-conversations/") + segment(recipient) + "/messages"
        found, seen_cursors, cursor = {}, set(), None
        for _ in range(max_pages):
            params = {"pageSize": page_size}
            if cursor: params["beforeMessageId" if direction=="older" else "afterMessageId"] = cursor
            data = self.api.request(actor, "GET", path, params=params)
            require(isinstance(data, dict) and isinstance(data.get("messages"), list), "Invalid message history")
            require(type(data.get("hasMore")) is bool, "Missing history hasMore")
            if data.get("resyncRequired"):
                raise Blocked("History requires resync; current snapshot cannot establish complete history")
            for item in data["messages"]:
                key = identifier(item.get("messageId"))
                require(key not in found, "Duplicate message across history pages")
                found[key] = item
            if not data["hasMore"]:
                require(set(expected_ids) <= found.keys(), "Target messages missing from available history window")
                return found
            cursor = data.get("oldestReturnedMessageId" if direction=="older" else "latestReturnedMessageId")
            require(cursor and cursor not in seen_cursors, "History cursor missing or repeated")
            seen_cursors.add(cursor)
        raise AssertionError("History page bound reached")

    def follow_status(self, actor, target):
        return self.api.request(actor, "GET", "/api/v1/mobile/user-follows/" + segment(target) + "/status")

    def set_follow(self, actor, target, enabled):
        before = self.follow_status(actor, target)
        require(type(before.get("following")) is bool, "Missing following flag")
        if before["following"] != enabled:
            self.api.request(actor, "POST" if enabled else "DELETE",
                "/api/v1/mobile/user-follows" + ("" if enabled else "/" + segment(target)),
                body={"targetUserId": target} if enabled else None)
        wait(lambda: self.follow_status(actor, target), lambda x: x.get("following") is enabled)

    def group(self, actor, group_id):
        data=self.api.request(actor, "GET", ROOT + "/chatrooms/" + segment(group_id))
        require(isinstance(data,dict) and isinstance(data.get("chatroom"),dict),"Invalid group detail wrapper")
        require(str(data["chatroom"].get("chatroomId"))==str(group_id),"Group detail ID mismatch")
        return data["chatroom"]

    def members(self, actor, group_id, *, keyword=None):
        return self.api.pages(actor, ROOT + "/chatrooms/" + segment(group_id) + ("/members/search" if keyword is not None else "/members"),
                              params={"keyword": keyword} if keyword is not None else {}, id_key="memberUserId", mode="cursor")

    def create_group(self, actor, name, *, client_group_id=None):
        body={"name":name,"inviteeUserIds":[]}
        if client_group_id:body["clientChatroomId"]=client_group_id
        data = self.api.request(actor, "POST", ROOT + "/chatrooms", body=body)
        identifier(data.get("chatroomId"))
        require(data.get("chatroomName") == name, "Created group name mismatch")
        return data

    def comment(self, actor, target_type, target_id, text, *, mentions=(), reply_to=None, on_created=None):
        path = ("/api/v1/mobile/ugc/comments/" + segment(reply_to) + "/replies" if reply_to else
                "/api/v1/mobile/ugc/comment-targets/" + segment(target_type) + "/" + segment(target_id) + "/comments")
        result = self.api.request(actor, "POST", path, body={"content": text,
            "mentions": [{"mentionedUserId": value, "sortOrder": i + 1} for i, value in enumerate(mentions)]})
        identifier(result.get("commentId"))
        if on_created is not None: on_created(result)
        require(result.get("content") == text, "Published comment content mismatch")
        require(result.get("moderationStatus") == "PASSED" and result.get("visibilityStatus") == "PUBLIC",
                "Comment is not published/public; cannot verify delivery")
        return result
