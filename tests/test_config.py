# tests/test_config.py
import pytest

from adaptive_mcp.config import Config, ConfigError, get_config, reset_config_cache


def _set_env(monkeypatch, **over):
    monkeypatch.delenv("ADAPTIVE_API_KEY", raising=False)
    for k, v in over.items():
        monkeypatch.setenv(k, v)
    reset_config_cache()


def test_requires_api_key(monkeypatch):
    _set_env(monkeypatch)
    with pytest.raises(ConfigError):
        Config.from_env()


def test_defaults(monkeypatch):
    _set_env(monkeypatch, ADAPTIVE_API_KEY="tok")
    cfg = Config.from_env()
    assert cfg.api_key == "tok"
    assert cfg.base_url == "https://api.adaptivesecurity.com"
    assert cfg.timeout == 60.0
    assert cfg.log_level == "INFO"
    assert cfg.http_host == "127.0.0.1"
    assert cfg.http_port == 8765


def test_base_url_trailing_slash_trimmed(monkeypatch):
    _set_env(monkeypatch, ADAPTIVE_API_KEY="tok", ADAPTIVE_BASE_URL="https://x.example/")
    assert Config.from_env().base_url == "https://x.example"


def test_bad_base_url_scheme(monkeypatch):
    _set_env(monkeypatch, ADAPTIVE_API_KEY="tok", ADAPTIVE_BASE_URL="ftp://nope")
    with pytest.raises(ConfigError):
        Config.from_env()


def test_bad_timeout(monkeypatch):
    _set_env(monkeypatch, ADAPTIVE_API_KEY="tok", ADAPTIVE_TIMEOUT="abc")
    with pytest.raises(ConfigError):
        Config.from_env()


def test_get_config_is_cached(monkeypatch):
    _set_env(monkeypatch, ADAPTIVE_API_KEY="tok")
    assert get_config() is get_config()
