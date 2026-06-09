from fastmcp import FastMCP

import adaptive_mcp.tools.request as request_tool


async def test_adaptive_request_registered_and_forwards(monkeypatch):
    seen = {}

    async def fake_execute_request(path, params=None):
        seen["path"] = path
        seen["params"] = params
        return {"ok": True}

    monkeypatch.setattr(request_tool, "execute_request", fake_execute_request)

    mcp = FastMCP(name="test")
    request_tool.register(mcp)
    tools = await mcp.get_tools()
    assert "adaptive_request" in tools

    out = await tools["adaptive_request"].fn(path="/v2/groups", params={"page_size": 5})
    assert out == {"ok": True}
    assert seen["path"] == "/v2/groups"
    assert seen["params"] == {"page_size": 5}


async def test_adaptive_request_accepts_stringified_params(monkeypatch):
    """The MCP client may stringify the params object; the tool must accept it
    and forward it (execute_request coerces the string back to a dict)."""
    seen = {}

    async def fake_execute_request(path, params=None):
        seen["params"] = params
        return {"ok": True}

    monkeypatch.setattr(request_tool, "execute_request", fake_execute_request)

    mcp = FastMCP(name="test")
    request_tool.register(mcp)
    tools = await mcp.get_tools()
    # A JSON string must not be rejected by the tool's parameter validation.
    out = await tools["adaptive_request"].fn(path="/v2/groups", params='{"page_size": 5}')
    assert out == {"ok": True}
    assert seen["params"] == '{"page_size": 5}'
