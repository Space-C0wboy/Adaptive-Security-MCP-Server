# tests/test_errors.py
from adaptive_mcp.errors import AdaptiveAPIError


def test_api_error_attributes_and_str():
    err = AdaptiveAPIError(401, "unauthorized", body={"message": "bad token"})
    assert err.status_code == 401
    assert err.message == "unauthorized"
    assert err.body == {"message": "bad token"}
    assert "401" in str(err)
    assert "unauthorized" in str(err)


def test_api_error_body_optional():
    err = AdaptiveAPIError(0, "Network error: boom")
    assert err.body is None
    assert err.status_code == 0
