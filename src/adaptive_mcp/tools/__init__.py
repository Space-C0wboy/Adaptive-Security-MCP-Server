"""Tool registry for the Adaptive MCP server.

Single entry point that wires every callable tool into the FastMCP server:
1. ``GENERATED_MODULES`` — one module per OpenAPI tag (audit_logs, groups,
   phishing, training, users), each exposing ``register(mcp)``.
2. ``request`` — the generic ``adaptive_request`` GET escape hatch.
"""

from __future__ import annotations

from fastmcp import FastMCP

from . import request
from ._generated import GENERATED_MODULES


def register_all(mcp: FastMCP) -> None:
    """Register every available tool on the given FastMCP server."""
    for module in GENERATED_MODULES:
        module.register(mcp)
    request.register(mcp)
