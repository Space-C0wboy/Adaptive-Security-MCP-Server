# tests/test_client.py
import httpx
import pytest

from adaptive_mcp.client import _MAX_RETRY_AFTER_SECONDS, AdaptiveClient, _parse_retry_after
from adaptive_mcp.config import Config
from adaptive_mcp.errors import AdaptiveAPIError


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch):
    """Make retry backoff instant so tests don't actually sleep."""
    async def _instant(_seconds):
        return None
    import adaptive_mcp.client as client_mod
    monkeypatch.setattr(client_mod.asyncio, "sleep", _instant)


def _cfg(**over):
    base = dict(
        api_key="tok",
        base_url="https://api.example.com",
        timeout=5.0,
        log_level="INFO",
        http_host="127.0.0.1",
        http_port=8765,
    )
    base.update(over)
    return Config(**base)


async def test_get_returns_json_and_sends_bearer(httpx_mock):
    httpx_mock.add_response(json={"data": [], "page": {}})
    client = AdaptiveClient(_cfg())
    out = await client.request("/v2/users", params={"page_size": 10})
    assert out == {"data": [], "page": {}}
    req = httpx_mock.get_request()
    assert req.headers["authorization"] == "Bearer tok"
    assert str(req.url) == "https://api.example.com/v2/users?page_size=10"
    await client.close()


async def test_http_error_raises_with_message(httpx_mock):
    httpx_mock.add_response(status_code=401, json={"message": "unauthorized"})
    client = AdaptiveClient(_cfg())
    with pytest.raises(AdaptiveAPIError) as ei:
        await client.request("/v2/users")
    assert ei.value.status_code == 401
    assert "unauthorized" in ei.value.message
    await client.close()


async def test_retries_on_503_then_succeeds(httpx_mock):
    httpx_mock.add_response(status_code=503)
    httpx_mock.add_response(json={"ok": True})
    client = AdaptiveClient(_cfg())
    out = await client.request("/v2/users")
    assert out == {"ok": True}
    assert len(httpx_mock.get_requests()) == 2
    await client.close()


async def test_retries_on_network_error_then_succeeds(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("boom"))
    httpx_mock.add_response(json={"ok": True})
    client = AdaptiveClient(_cfg())
    out = await client.request("/v2/users")
    assert out == {"ok": True}
    assert len(httpx_mock.get_requests()) == 2
    await client.close()


async def test_raises_after_exhausting_retries_on_5xx(httpx_mock):
    for _ in range(3):
        httpx_mock.add_response(status_code=503)
    client = AdaptiveClient(_cfg())
    with pytest.raises(AdaptiveAPIError) as ei:
        await client.request("/v2/users")
    assert ei.value.status_code == 503
    assert len(httpx_mock.get_requests()) == 3
    await client.close()


async def test_non_json_success_body_raises(httpx_mock):
    httpx_mock.add_response(status_code=200, text="not json", headers={"content-type": "text/plain"})
    client = AdaptiveClient(_cfg())
    with pytest.raises(AdaptiveAPIError):
        await client.request("/v2/users")
    await client.close()


def test_parse_retry_after_seconds_and_cap():
    assert _parse_retry_after("2") == 2.0
    assert _parse_retry_after(None) is None
    assert _parse_retry_after("not-a-date") is None
    assert _parse_retry_after("120") == 120.0
    assert _MAX_RETRY_AFTER_SECONDS == 60.0
