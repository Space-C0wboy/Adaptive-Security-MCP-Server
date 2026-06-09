from adaptive_mcp.tools import _common


def test_drop_none_removes_unset():
    assert _common.drop_none({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}


def test_drop_none_empty():
    assert _common.drop_none({}) == {}


async def test_execute_request_forwards_path_and_params(monkeypatch):
    seen = {}

    class FakeClient:
        async def request(self, path, *, params=None):
            seen["path"] = path
            seen["params"] = params
            return {"ok": True}

    async def fake_get_client():
        return FakeClient()

    monkeypatch.setattr(_common, "get_client", fake_get_client)
    out = await _common.execute_request("/v2/users", {"page_size": 10, "page_after": None})
    assert out == {"ok": True}
    assert seen["path"] == "/v2/users"
    # None values are dropped before the request is sent.
    assert seen["params"] == {"page_size": 10}


async def test_execute_request_no_params(monkeypatch):
    seen = {}

    class FakeClient:
        async def request(self, path, *, params=None):
            seen["params"] = params
            return {}

    async def fake_get_client():
        return FakeClient()

    monkeypatch.setattr(_common, "get_client", fake_get_client)
    await _common.execute_request("/v2/users/1")
    assert seen["params"] == {}
