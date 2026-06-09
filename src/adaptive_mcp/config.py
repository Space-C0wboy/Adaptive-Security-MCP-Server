"""Server configuration, loaded once from the environment.

Everything controlling how the MCP server connects to the Adaptive API and how it
behaves is sourced from environment variables here (with optional ``.env`` support
via python-dotenv for local development). Values are parsed and validated up front
into an immutable ``Config`` dataclass so the rest of the codebase relies on a
single, already-validated source of truth.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load a local .env (if present) into os.environ at import time.
load_dotenv()


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid.

    Distinct from runtime API errors: this signals a setup/deployment problem
    (e.g. a missing API key) that must be fixed before the server can start.
    """


@dataclass(frozen=True)
class Config:
    """Immutable, validated snapshot of the server's runtime configuration."""

    api_key: str  # ADAPTIVE_API_KEY — bearer token (required)
    base_url: str  # ADAPTIVE_BASE_URL — API root, trailing slash trimmed
    timeout: float  # ADAPTIVE_TIMEOUT — per-request timeout in seconds
    log_level: str  # LOG_LEVEL — standard logging level name, upper-cased
    http_host: str  # MCP_HTTP_HOST — bind host for the HTTP transport
    http_port: int  # MCP_HTTP_PORT — bind port for the HTTP transport

    @classmethod
    def from_env(cls) -> Config:
        """Build a ``Config`` by reading and validating environment variables.

        Raises:
            ConfigError: if the API key is missing, the base URL is malformed, or
                a numeric field cannot be parsed. Validation happens here so
                misconfiguration fails fast at startup.
        """
        api_key = os.getenv("ADAPTIVE_API_KEY", "").strip()
        if not api_key:
            raise ConfigError(
                "ADAPTIVE_API_KEY is required. Set it in your environment or .env file."
            )

        base_url = (
            os.getenv("ADAPTIVE_BASE_URL", "https://api.adaptivesecurity.com")
            .strip()
            .rstrip("/")
        )
        if not base_url.startswith(("http://", "https://")):
            raise ConfigError(
                f"ADAPTIVE_BASE_URL must start with http:// or https:// (got {base_url!r})"
            )

        try:
            timeout = float(os.getenv("ADAPTIVE_TIMEOUT", "60"))
        except ValueError as e:
            raise ConfigError(f"ADAPTIVE_TIMEOUT must be a number: {e}") from e

        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        http_host = os.getenv("MCP_HTTP_HOST", "127.0.0.1")
        try:
            http_port = int(os.getenv("MCP_HTTP_PORT", "8765"))
        except ValueError as e:
            raise ConfigError(f"MCP_HTTP_PORT must be an integer: {e}") from e

        return cls(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            log_level=log_level,
            http_host=http_host,
            http_port=http_port,
        )


_config: Config | None = None


def get_config() -> Config:
    """Return the process-wide ``Config``, building it on first use."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reset_config_cache() -> None:
    """Clear the cached config so the next ``get_config()`` re-reads the env.

    Intended for tests that tweak environment variables.
    """
    global _config
    _config = None
