"""Adaptive MCP server — entrypoint.

Wires everything into a runnable Model Context Protocol server exposing the
Adaptive Security Awareness Training API to AI assistants. Intentionally small:
the heavy lifting lives in sibling modules.
"""

from __future__ import annotations

import argparse
import logging
import sys

from fastmcp import FastMCP

from .client import shutdown_client
from .config import ConfigError, get_config
from .tools import register_all


def build_server() -> FastMCP:
    """Construct, configure, and fully populate the FastMCP server.

    Raises:
        ConfigError: from ``get_config()`` if required env settings (e.g. the API
            key) are missing — called first so misconfiguration fails fast.
    """
    config = get_config()  # validates env early

    # Logging MUST go to stderr: under the stdio transport, stdout is the JSON-RPC
    # channel, so any log line there would corrupt the protocol stream.
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    mcp = FastMCP(
        name="adaptive-mcp",
        instructions=(
            "MCP server for the Adaptive Security Awareness Training API (v2). Tools "
            "are grouped by domain: Audit Logs, Groups, Phishing, Training, and Users. "
            "List endpoints are cursor-paginated — pass `page_after`/`page_size` and "
            "read the returned page cursor. Use `adaptive_request` for any read "
            "endpoint without a dedicated tool. The API is read-only (GET only)."
        ),
    )
    register_all(mcp)
    return mcp


def main() -> int:
    """CLI entrypoint: parse arguments, run the server, and clean up."""
    parser = argparse.ArgumentParser(prog="adaptive-mcp")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    try:
        mcp = build_server()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2

    config = get_config()
    try:
        if args.transport == "stdio":
            mcp.run(transport="stdio")
        else:
            mcp.run(
                transport="http",
                host=args.host or config.http_host,
                port=args.port or config.http_port,
            )
    finally:
        import asyncio

        try:
            asyncio.run(shutdown_client())
        except RuntimeError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
