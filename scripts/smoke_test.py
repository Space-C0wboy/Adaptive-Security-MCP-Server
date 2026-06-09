"""Manual live smoke test — hits the real Adaptive API using .env credentials.

Read-only: lists users and phishing campaigns. Run with `uv run python
scripts/smoke_test.py`. Not part of the automated test suite.
"""

from __future__ import annotations

import asyncio

from adaptive_mcp.client import get_client, shutdown_client


async def main() -> None:
    client = await get_client()
    try:
        users = await client.request("/v2/users", params={"page_size": 2})
        print("users keys:", list(users) if isinstance(users, dict) else type(users))
        campaigns = await client.request("/v2/phishing/campaigns", params={"page_size": 2})
        print("phishing campaigns keys:", list(campaigns) if isinstance(campaigns, dict) else type(campaigns))
        print("SMOKE TEST OK")
    finally:
        await shutdown_client()


if __name__ == "__main__":
    asyncio.run(main())
