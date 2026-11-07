from copy import deepcopy
import pytest
from velowind_api.auth import Identity
from velowind_api.history import History


def page(ids, more=False, cursor=None, resync=False):
    return {"messages": [{"messageId": x} for x in ids], "hasMore": more,
            "latestReturnedMessageId": cursor or (ids[-1] if ids else None), "resyncRequired": resync}


class Pages:
    def __init__(self, pages):
        self.pages, self.calls = iter(pages), []

    def request(self, *args, **kwargs):
        self.calls.append(kwargs.get("params"))
        return deepcopy(next(self.pages))


def test_forward_pagination():
    client = Pages([page(["1"], True), page(["2"])])
    result = History(client, Identity("b", "token")).find("a", ["1", "2"])
    assert set(result) == {"1", "2"}
    assert client.calls[1]["afterMessageId"] == "1"


@pytest.mark.parametrize("pages", [
    [page(["1"], True), page([], True, "1")],
    [page(["1"], True), page(["1"])],
    [page([])],
    [page([], True)],
    [page(["1"], True, resync=True), page(["2"], resync=True)],
])
def test_incomplete_or_invalid_history_fails(pages):
    with pytest.raises(AssertionError):
        History(Pages(pages), Identity("b", "token")).find("a", ["1", "2"])


def test_recovery_replaces_partial_snapshot():
    client = Pages([page(["old"], True), page(["new"], resync=True)])
    assert set(History(client, Identity("b", "token")).find("a", ["new"])) == {"new"}
    client = Pages([page(["old"], True), page(["new"], resync=True)])
    with pytest.raises(AssertionError, match="missing"):
        History(client, Identity("b", "token")).find("a", ["old", "new"])


def test_page_limit_is_failure():
    with pytest.raises(AssertionError, match="page limit"):
        History(Pages([page(["1"], True)]), Identity("b", "token"), max_pages=1).find("a", ["2"])
