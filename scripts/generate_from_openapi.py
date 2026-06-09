"""Generate FastMCP tool modules from the Adaptive API OpenAPI spec.

This MCP server exposes the Adaptive REST API to MCP clients as a set of typed
tools. Rather than hand-write a tool per endpoint, we treat the vendor's OpenAPI
document as the source of truth and *generate* one FastMCP tool module per
OpenAPI tag.

What this script produces, given the spec:
  - src/adaptive_mcp/tools/_generated/<tag>.py — one module per OpenAPI tag, each
    exposing a `register(mcp)` that wires up that tag's tools.
  - src/adaptive_mcp/tools/_generated/__init__.py — imports every module and lists
    them in GENERATED_MODULES so the server can register them all in one pass.
  - docs/ENDPOINTS.md — a human-readable catalog of every generated tool.

Usage:
    python scripts/generate_from_openapi.py [SPEC_JSON]

Defaults to "Source Material/openapi.json".

Determinism: the same spec must always yield byte-identical output, so modules and
operations are sorted into a fixed order and files are written with explicit LF
newlines.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DEFAULT_SPEC = Path("Source Material/openapi.json")
DEFAULT_OUT_DIR = Path("src/adaptive_mcp/tools/_generated")
DEFAULT_DOC = Path("docs/ENDPOINTS.md")

# The Adaptive API is read-only and the client only issues GET, so we generate
# tools for GET endpoints only. Other methods would produce tools that silently
# issue a GET — restrict here to make the invariant explicit.
_HTTP_METHODS = ("get",)

# OpenAPI scalar type -> Python annotation. Unknown/absent types -> Any.
_TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list",
}

# Optional per-operation description overrides, keyed by operationId. Only the
# description text is overridden; signatures are always derived from the spec.
OVERRIDES: dict[str, str] = {}


def tool_name(op_id: str) -> str:
    """Convert a camelCase operationId to a snake_case MCP tool name."""
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", op_id)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


def module_name(tag: str) -> str:
    """Convert an OpenAPI tag into a valid snake_case module filename stem."""
    s = tag.strip().replace("-", " ").replace("/", " ")
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"[^a-z0-9_]", "", s.lower())
    s = re.sub(r"_+", "_", s).strip("_")
    if not s or s[0].isdigit():
        s = "mod_" + s
    return s


def py_type(schema: dict, *, required: bool) -> str:
    """Map an OpenAPI parameter schema to a Python annotation string.

    Array params also accept ``str`` because MCP clients sometimes serialize a
    list argument as a JSON string; ``execute_request`` coerces it back to a list
    (see ``coerce_json``). Without ``| str`` the transport would reject the string
    before our code runs.
    """
    base = _TYPE_MAP.get((schema or {}).get("type"), "Any")
    if base == "list":
        return "list | str" if required else "list | str | None"
    return base if required else f"{base} | None"


def _default_literal(schema: dict) -> str:
    """Return the Python literal for a query param's default (``None`` if absent)."""
    if schema and "default" in schema:
        return repr(schema["default"])
    return "None"


def collect(spec: dict) -> dict[str, list[dict]]:
    """Parse every GET operation into normalized per-module op records.

    Returns an ordered dict: module name -> list of op dicts (op_id, method, path,
    summary, path_params, query_params), sorted deterministically.

    Raises:
        ValueError: if two operations share an operationId (would collide on a
            tool name).
    """
    by_module: dict[str, list[dict]] = {}
    seen: set[str] = set()
    seen_tool_names: set[str] = set()
    for path in sorted(spec.get("paths", {})):
        item = spec["paths"][path]
        for method in _HTTP_METHODS:
            op = item.get(method)
            if not op:
                continue
            op_id = op.get("operationId")
            if not op_id:
                continue
            if op_id in seen:
                raise ValueError(f"Duplicate operationId: {op_id!r}")
            seen.add(op_id)
            tname = tool_name(op_id)
            if tname in seen_tool_names:
                raise ValueError(
                    f"Duplicate tool name {tname!r} (from operationId {op_id!r})"
                )
            seen_tool_names.add(tname)
            tags = op.get("tags") or ["Misc"]
            mod = module_name(tags[0])
            params = op.get("parameters", [])
            path_params = [p for p in params if p.get("in") == "path"]
            query_params = [p for p in params if p.get("in") == "query"]
            by_module.setdefault(mod, []).append(
                {
                    "op_id": op_id,
                    "method": method,
                    "path": path,
                    "summary": op.get("summary", "") or "",
                    "tag": tags[0],
                    "path_params": path_params,
                    "query_params": query_params,
                }
            )
    for ops in by_module.values():
        ops.sort(key=lambda o: tool_name(o["op_id"]))
    return dict(sorted(by_module.items()))


_HEADER = '''"""Adaptive MCP tools for domain: {tag}.

GENERATED by scripts/generate_from_openapi.py — DO NOT EDIT BY HAND.
Any manual change here will be overwritten the next time the generator runs; to
change a tool, edit the generator (or the source OpenAPI spec) and regenerate via:
    python scripts/generate_from_openapi.py

Each generated tool is a thin async wrapper: it accepts typed parameters (path
params interpolated into the URL, query params forwarded as the query string) and
calls `execute_request`, which performs the actual HTTP GET.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from .._common import execute_request


def register(mcp: FastMCP) -> None:
'''


def _path_expr(path: str, path_params: list[dict]) -> str:
    """Return the Python expression for the request path.

    With path params, an f-string literal (the OpenAPI ``{name}`` placeholders are
    already valid f-string fields since param names are Python identifiers); with
    none, a plain string literal.
    """
    if path_params:
        return "f" + json.dumps(path)
    return json.dumps(path)


def _emit_tool(op: dict) -> str:
    """Render the Python source for one FastMCP tool from a collected op record."""
    name = tool_name(op["op_id"])
    summary = op["summary"] or op["op_id"]
    path = op["path"]
    pps = op["path_params"]
    qps = op["query_params"]

    # Description: override if present, else summary + method/path + param hint.
    desc = OVERRIDES.get(op["op_id"]) or summary
    param_names = [p["name"] for p in pps] + [p["name"] for p in qps]
    hint = f" GET {path}."
    if param_names:
        hint += " Params: " + ", ".join(param_names) + "."
    description = json.dumps(desc + hint)

    # Parameters: required path params first (no default), then optional query params.
    lines: list[str] = []
    for p in pps:
        ann = py_type(p.get("schema", {}), required=True)
        pdesc = json.dumps(f"Path param: {p['name']} ({(p.get('schema') or {}).get('type', 'string')})")
        lines.append(
            f"        {p['name']}: Annotated[{ann}, Field(description={pdesc})],"
        )
    for p in qps:
        schema = p.get("schema", {})
        ann = py_type(schema, required=False)
        default = _default_literal(schema)
        pdesc = json.dumps(f"Query param: {p['name']} ({schema.get('type', 'string')})")
        lines.append(
            f"        {p['name']}: Annotated[{ann}, Field(default={default}, description={pdesc})] = {default},"
        )
    params_block = "\n".join(lines)

    # Body: build the path expr and (when there are query params) the params dict.
    path_expr = _path_expr(path, pps)
    if qps:
        pairs = ", ".join(f'"{p["name"]}": {p["name"]}' for p in qps)
        body = f"        return await execute_request({path_expr}, {{{pairs}}})"
    else:
        body = f"        return await execute_request({path_expr})"

    return (
        f'    # {op["op_id"]} ({op["method"].upper()} {path}) — tool name "{name}"\n'
        f'    @mcp.tool(name="{name}", description={description})\n'
        f"    async def {name}(\n"
        f"{params_block}\n"
        f"    ) -> Any:\n"
        f"{body}\n"
    )


def _emit_module(mod: str, ops: list[dict]) -> str:
    """Render a full generated module's source."""
    tag = ops[0]["tag"] if ops else mod
    out = _HEADER.replace("{tag}", tag)
    out += "\n".join(_emit_tool(op) for op in ops)
    return out


def generate(
    *,
    spec_path: Path = DEFAULT_SPEC,
    out_dir: Path = DEFAULT_OUT_DIR,
    endpoints_doc: Path = DEFAULT_DOC,
) -> None:
    """Generate all tool modules, the package __init__, and the docs catalog."""
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    by_module = collect(spec)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for mod, ops in by_module.items():
        (out_dir / f"{mod}.py").write_text(_emit_module(mod, ops), encoding="utf-8", newline="\n")

    # __init__.py importing every module and listing GENERATED_MODULES.
    mods = sorted(by_module)
    init_lines = ['"""Generated Adaptive tool modules. Do not edit by hand."""', "", "from . import ("]
    init_lines += [f"    {m}," for m in mods]
    init_lines += [")", "", "GENERATED_MODULES = ["]
    init_lines += [f"    {m}," for m in mods]
    init_lines += ["]", ""]
    (out_dir / "__init__.py").write_text("\n".join(init_lines), encoding="utf-8", newline="\n")

    # docs/ENDPOINTS.md catalog.
    doc_lines = [
        "# Adaptive MCP — Tool Catalog",
        "",
        "Generated by `scripts/generate_from_openapi.py`. Do not edit by hand.",
        "",
        "| Tool | Method · Path | Domain |",
        "|------|---------------|--------|",
    ]
    for mod in mods:
        for op in by_module[mod]:
            doc_lines.append(
                f"| `{tool_name(op['op_id'])}` | {op['method'].upper()} `{op['path']}` | {op['tag']} |"
            )
    doc_lines.append("")
    Path(endpoints_doc).parent.mkdir(parents=True, exist_ok=True)
    Path(endpoints_doc).write_text("\n".join(doc_lines), encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    spec_path = Path(argv[0]) if argv else DEFAULT_SPEC
    generate(spec_path=spec_path)
    print(f"Generated tools from {spec_path} into {DEFAULT_OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
