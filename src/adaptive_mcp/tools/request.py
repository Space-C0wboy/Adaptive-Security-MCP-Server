"""The generic ``adaptive_request`` escape-hatch tool.

Not every Adaptive endpoint necessarily has a dedicated generated tool. This
catch-all runs a raw ``GET`` against an arbitrary path so an AI assistant can
reach any read endpoint, including ones added after the tools were generated.
The Adaptive API is entirely read-only, so this is GET-only by construction.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from ._common import execute_request


def register(mcp: FastMCP) -> None:
    """Register the ``adaptive_request`` tool on the FastMCP server."""

    @mcp.tool(
        name="adaptive_request",
        description=(
            "Issue a raw GET request against the Adaptive API for endpoints not "
            "covered by a dedicated tool. Provide the path (e.g. '/v2/users' or "
            "'/v2/users/{id}') and an optional dict of query parameters. The "
            "Adaptive API is read-only, so only GET is supported."
        ),
    )
    async def adaptive_request(
        path: Annotated[
            str,
            Field(description="Request path beginning with '/', e.g. '/v2/phishing/campaigns'."),
        ],
        params: Annotated[
            dict | str | None,
            Field(
                default=None,
                description=(
                    "Optional query parameters as a JSON object "
                    "(e.g. {\"page_size\": 50}). A JSON string is also accepted."
                ),
            ),
        ] = None,
    ) -> Any:
        # ``params`` may arrive as a real dict or as a JSON string the MCP client
        # stringified; ``execute_request`` coerces a string back to a dict.
        return await execute_request(path, params)
