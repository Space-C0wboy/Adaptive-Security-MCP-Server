from adaptive_mcp.tools import _common


def test_drop_none_removes_unset():
    assert _common.drop_none({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}


def test_drop_none_empty():
    assert _common.drop_none({}) == {}


def test_coerce_json_parses_list_and_object():
    assert _common.coerce_json('["a","b"]') == ["a", "b"]
    assert _common.coerce_json('{"page_size": 5}') == {"page_size": 5}


def test_coerce_json_passes_scalars_through():
    # Plain ids/cursors/dates are not JSON containers — leave untouched.
    assert _common.coerce_json("HOST01") == "HOST01"
    assert _common.coerce_json("2026-06-01") == "2026-06-01"
    assert _common.coerce_json(5) == 5
    assert _common.coerce_json(None) is None
    # Looks like JSON but isn't valid — return the original string unchanged.
    assert _common.coerce_json("[not json") == "[not json"


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


async def test_execute_request_coerces_stringified_params(monkeypatch):
    """A client that stringifies the whole params object is recovered."""
    seen = {}

    class FakeClient:
        async def request(self, path, *, params=None):
            seen["params"] = params
            return {}

    async def fake_get_client():
        return FakeClient()

    monkeypatch.setattr(_common, "get_client", fake_get_client)
    await _common.execute_request("/v2/users", '{"page_size": 50}')
    assert seen["params"] == {"page_size": 50}


async def test_execute_request_coerces_stringified_list_value(monkeypatch):
    """A list value stringified by the client (e.g. audit-log actions) is recovered."""
    seen = {}

    class FakeClient:
        async def request(self, path, *, params=None):
            seen["params"] = params
            return {}

    async def fake_get_client():
        return FakeClient()

    monkeypatch.setattr(_common, "get_client", fake_get_client)
    await _common.execute_request("/v2/audit-logs", {"actions": '["CREATED_API_KEY"]'})
    assert seen["params"] == {"actions": ["CREATED_API_KEY"]}
