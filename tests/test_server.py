# tests/test_server.py
import pytest

from adaptive_mcp import server
from adaptive_mcp.config import reset_config_cache


async def test_build_server_registers_tools(monkeypatch):
    monkeypatch.setenv("ADAPTIVE_API_KEY", "tok")
    reset_config_cache()
    mcp = server.build_server()
    tools = await mcp.get_tools()
    assert "list_users" in tools
    assert "adaptive_request" in tools


def test_build_server_requires_api_key(monkeypatch):
    monkeypatch.delenv("ADAPTIVE_API_KEY", raising=False)
    reset_config_cache()
    from adaptive_mcp.config import ConfigError

    with pytest.raises(ConfigError):
        server.build_server()
