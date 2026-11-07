"""Business assertions shared by flows and standalone API consumers."""


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def identifier(value, field):
    require(type(value) in (str, int) and bool(str(value).strip()), f"Missing/invalid {field}")
    return str(value)


def peer(items, user_id, required=True):
    matches = [item for item in items if str(item.get("peerUserId")) == str(user_id)]
    require(len(matches) <= 1, "Duplicate peer in conversation list")
    if required:
        require(bool(matches), "Expected peer absent from conversation list")
    return matches[0] if matches else None


def unread(item):
    value = item.get("unreadCount") if item else 0
    require(type(value) is int and value >= 0, "Invalid unreadCount")
    return value


def pinned(items, user_id):
    require(peer(items, user_id).get("pinned") is True, "Target conversation is not pinned")
    seen_unpinned = False
    for item in items:
        require(type(item.get("pinned")) is bool, "Invalid pinned flag")
        if item["pinned"]:
            require(not seen_unpinned, "Pinned conversation sorted after unpinned conversation")
        else:
            seen_unpinned = True


def card(message, kind, biz_id):
    value = message.get("contextCard")
    require(isinstance(value, dict), "Missing contextCard")
    require(value.get("contextType") == kind, "Wrong card contextType")
    require(str(value.get("bizId")) == str(biz_id), "Wrong card bizId")
    if kind == "POST":
        require(value.get("bizType") == "POST", "Wrong POST card bizType")


def message(actual, sender, receiver, content, client_id, message_id=None, *, recipient_view=False):
    identifier(actual.get("messageId"), "messageId")
    identifier(actual.get("conversationId"), "conversationId")
    require(str(actual.get("senderUserId")) == str(sender), "Wrong message sender")
    require(str(actual.get("receiverUserId")) == str(receiver), "Wrong message receiver")
    require(actual.get("contentType") == "TEXT", "Wrong message contentType")
    require(actual.get("content") == content, "Message content mismatch")
    if recipient_view:
        require(actual.get("direction") == "INBOUND", "Wrong recipient message direction")
        require(actual.get("clientMessageId") is None, "Recipient must not expose sender clientMessageId")
    else:
        require(actual.get("clientMessageId") == client_id, "clientMessageId mismatch")
    if message_id is not None:
        require(str(actual.get("messageId")) == str(message_id), "messageId mismatch")
