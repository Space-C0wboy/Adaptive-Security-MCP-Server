import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path("scripts/generate_from_openapi.py")
FIXTURE = Path("tests/fixtures/mini_openapi.json")


def _load_generator():
    spec = importlib.util.spec_from_file_location("gen", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_tool_name_snake_case():
    gen = _load_generator()
    assert gen.tool_name("listUsers") == "list_users"
    assert gen.tool_name("getUser") == "get_user"
    assert gen.tool_name("getGroupMembers") == "get_group_members"
    assert gen.tool_name("getTrainingCampaignEnrollments") == "get_training_campaign_enrollments"


def test_module_name():
    gen = _load_generator()
    assert gen.module_name("Audit Logs") == "audit_logs"
    assert gen.module_name("Phishing") == "phishing"
    name = gen.module_name("123 Weird")
    assert name.isidentifier() and not name[0].isdigit()


def test_py_type_mapping():
    gen = _load_generator()
    assert gen.py_type({"type": "string"}, required=True) == "str"
    assert gen.py_type({"type": "string"}, required=False) == "str | None"
    assert gen.py_type({"type": "integer"}, required=False) == "int | None"
    assert gen.py_type({"type": "boolean"}, required=False) == "bool | None"
    assert gen.py_type({"type": "array"}, required=False) == "list | None"
    assert gen.py_type({}, required=False) == "Any | None"


def test_generate_writes_modules(tmp_path):
    gen = _load_generator()
    out_dir = tmp_path / "_generated"
    docs = tmp_path / "ENDPOINTS.md"
    gen.generate(spec_path=FIXTURE, out_dir=out_dir, endpoints_doc=docs)

    users = (out_dir / "users.py").read_text()
    assert "def register(mcp" in users
    assert 'name="list_users"' in users
    assert 'name="get_user"' in users
    # path param interpolated via f-string, query params forwarded
    assert 'f"/v2/users/{userId}"' in users
    assert '"/v2/users"' in users

    init = (out_dir / "__init__.py").read_text()
    assert "GENERATED_MODULES" in init
    assert "users" in init and "audit_logs" in init

    assert docs.read_text().count("list_users") >= 1

    # non-None query-param default is emitted
    assert "default=100" in users
    # array-typed query param maps to list | None (audit_logs module from the "Audit Logs" tag)
    audit = (out_dir / "audit_logs.py").read_text()
    assert "list | None" in audit


def test_generated_modules_compile(tmp_path):
    gen = _load_generator()
    out_dir = tmp_path / "_generated"
    gen.generate(spec_path=FIXTURE, out_dir=out_dir, endpoints_doc=tmp_path / "E.md")
    for py in out_dir.glob("*.py"):
        compile(py.read_text(), str(py), "exec")


def test_duplicate_operation_id_raises(tmp_path):
    gen = _load_generator()
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Dup", "version": "v2"},
        "paths": {
            "/a": {"get": {"operationId": "dup", "tags": ["X"], "parameters": []}},
            "/b": {"get": {"operationId": "dup", "tags": ["X"], "parameters": []}},
        },
    }
    p = tmp_path / "dup.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(ValueError):
        gen.generate(spec_path=p, out_dir=tmp_path / "_g", endpoints_doc=tmp_path / "E.md")
