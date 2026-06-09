from fastmcp import FastMCP

from adaptive_mcp.tools import register_all

EXPECTED_TOOLS = {
    # Audit Logs
    "list_audit_logs", "get_audit_log",
    # Groups
    "list_groups", "get_group", "get_group_members",
    # Phishing
    "list_phishing_campaigns", "get_phishing_enrollments", "get_phishing_campaign",
    "list_campaign_simulations", "get_simulation",
    # Training
    "list_training_campaigns", "get_training_campaign_enrollments", "get_training_campaign",
    # Users
    "list_users", "get_user",
    # Escape hatch
    "adaptive_request",
}


async def test_all_tools_register():
    mcp = FastMCP(name="test")
    register_all(mcp)
    tools = await mcp.get_tools()
    assert EXPECTED_TOOLS.issubset(set(tools)), EXPECTED_TOOLS - set(tools)
    # 15 generated tools + 1 escape hatch — assert the LIVE registry count so a
    # future regeneration that adds an unexpected tool is caught here too.
    assert len(EXPECTED_TOOLS) == 16
    assert len(tools) == len(EXPECTED_TOOLS), f"unexpected tools: {set(tools) - EXPECTED_TOOLS}"


async def test_get_user_builds_path(monkeypatch):
    import adaptive_mcp.tools._common as common

    seen = {}

    class FakeClient:
        async def request(self, path, *, params=None):
            seen["path"] = path
            seen["params"] = params
            return {"id": "abc"}

    async def fake_get_client():
        return FakeClient()

    monkeypatch.setattr(common, "get_client", fake_get_client)

    mcp = FastMCP(name="test")
    register_all(mcp)
    tools = await mcp.get_tools()
    out = await tools["get_user"].fn(userId="abc")
    assert out == {"id": "abc"}
    assert seen["path"] == "/v2/users/abc"
