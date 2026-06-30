"""Core behavior tests for MCP client server config building."""

import os
from pathlib import Path

import pytest

from deerflow.config.extensions_config import ExtensionsConfig, McpServerConfig
from deerflow.mcp.client import build_server_params, build_servers_config


def test_build_server_params_stdio_success():
    config = McpServerConfig(
        type="stdio",
        command="npx",
        args=["-y", "my-mcp-server"],
        env={"API_KEY": "secret"},
    )

    params = build_server_params("my-server", config)

    assert params == {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "my-mcp-server"],
        "env": {"API_KEY": "secret"},
    }


def test_extensions_config_resolves_env_variables_inside_nested_collections(monkeypatch):
    monkeypatch.setenv("MCP_TOKEN", "secret")
    monkeypatch.delenv("MISSING_TOKEN", raising=False)
    raw_config = {
        "args": ["--token", "$MCP_TOKEN", {"nested": ["$MCP_TOKEN", "$MISSING_TOKEN"]}],
        "tuple_args": ("$MCP_TOKEN", "$MISSING_TOKEN"),
        "env": {"API_KEY": "$MCP_TOKEN"},
        "enabled": True,
        "timeout": 30,
    }

    resolved = ExtensionsConfig.resolve_env_variables(raw_config)

    assert resolved["args"] == ["--token", "secret", {"nested": ["secret", ""]}]
    assert resolved["tuple_args"] == ("secret", "")
    assert resolved["env"] == {"API_KEY": "secret"}
    assert resolved["enabled"] is True
    assert resolved["timeout"] == 30


def test_extensions_config_loads_enabled_registry_mcp_servers(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "extensions_config.json"
    config_path.write_text('{"mcpServers": {}, "skills": {}}', encoding="utf-8")
    manifest_path = tmp_path / "registry.json"
    manifest_path.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "mcp",
              "name": "local-docs",
              "enabled": true,
              "source": "local",
              "description": "Local docs MCP",
              "metadata": {
                "type": "stdio",
                "command": "python",
                "args": ["-m", "internal_mcps.docs"],
                "env": {"DOCS_ROOT": "$DOCS_ROOT"}
              }
            },
            {
              "kind": "mcp",
              "name": "disabled-docs",
              "enabled": false,
              "source": "local",
              "metadata": {
                "type": "stdio",
                "command": "python"
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("DEER_FLOW_EXTENSIONS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(manifest_path))
    monkeypatch.setenv("DOCS_ROOT", str(tmp_path / "docs"))

    config = ExtensionsConfig.from_file()

    assert sorted(config.mcp_servers) == ["local-docs"]
    assert config.mcp_servers["local-docs"].command == "python"
    assert config.mcp_servers["local-docs"].args == ["-m", "internal_mcps.docs"]
    assert config.mcp_servers["local-docs"].env == {"DOCS_ROOT": str(tmp_path / "docs")}
    assert config.mcp_servers["local-docs"].description == "Local docs MCP"


def test_extensions_config_file_mcp_servers_override_registry(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "extensions_config.json"
    config_path.write_text(
        """
        {
          "mcpServers": {
            "local-docs": {
              "type": "stdio",
              "command": "uvx",
              "args": ["company-docs"],
              "description": "Explicit config wins"
            }
          },
          "skills": {}
        }
        """,
        encoding="utf-8",
    )
    manifest_path = tmp_path / "registry.json"
    manifest_path.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "mcp",
              "name": "local-docs",
              "enabled": true,
              "source": "local",
              "metadata": {
                "type": "stdio",
                "command": "python",
                "args": ["-m", "internal_mcps.docs"]
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("DEER_FLOW_EXTENSIONS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(manifest_path))

    config = ExtensionsConfig.from_file()

    assert config.mcp_servers["local-docs"].command == "uvx"
    assert config.mcp_servers["local-docs"].args == ["company-docs"]
    assert config.mcp_servers["local-docs"].description == "Explicit config wins"


def test_build_servers_config_includes_registry_mcp_servers(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "extensions_config.json"
    config_path.write_text('{"mcpServers": {}, "skills": {}}', encoding="utf-8")
    manifest_path = tmp_path / "registry.json"
    manifest_path.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "mcp",
              "name": "local-docs",
              "enabled": true,
              "source": "local",
              "metadata": {
                "type": "stdio",
                "command": "python",
                "args": ["-m", "internal_mcps.docs"]
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("DEER_FLOW_EXTENSIONS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(manifest_path))

    servers = build_servers_config(ExtensionsConfig.from_file())

    assert servers == {
        "local-docs": {
            "transport": "stdio",
            "command": "python",
            "args": ["-m", "internal_mcps.docs"],
        }
    }


def test_mcp_cache_config_signature_tracks_registry_manifests(monkeypatch, tmp_path: Path):
    from deerflow.mcp import cache

    config_path = tmp_path / "extensions_config.json"
    config_path.write_text('{"mcpServers": {}, "skills": {}}', encoding="utf-8")
    manifest_path = tmp_path / "registry.json"
    manifest_path.write_text('{"version": 1, "extensions": []}', encoding="utf-8")
    monkeypatch.setenv("DEER_FLOW_EXTENSIONS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(manifest_path))

    first = cache._get_config_signature()
    os.utime(manifest_path, (manifest_path.stat().st_atime, manifest_path.stat().st_mtime + 10))
    second = cache._get_config_signature()

    assert first != second
    assert str(manifest_path) in {path for path, _mtime in second}


def test_build_server_params_stdio_requires_command():
    config = McpServerConfig(type="stdio", command=None)

    with pytest.raises(ValueError, match="requires 'command' field"):
        build_server_params("broken-stdio", config)


@pytest.mark.parametrize("transport", ["sse", "http"])
def test_build_server_params_http_like_success(transport: str):
    config = McpServerConfig(
        type=transport,
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer token"},
    )

    params = build_server_params("remote-server", config)

    assert params == {
        "transport": transport,
        "url": "https://example.com/mcp",
        "headers": {"Authorization": "Bearer token"},
    }


@pytest.mark.parametrize("transport", ["sse", "http"])
def test_build_server_params_http_like_requires_url(transport: str):
    config = McpServerConfig(type=transport, url=None)

    with pytest.raises(ValueError, match="requires 'url' field"):
        build_server_params("broken-remote", config)


def test_build_server_params_rejects_unsupported_transport():
    config = McpServerConfig(type="websocket")

    with pytest.raises(ValueError, match="unsupported transport type"):
        build_server_params("bad-transport", config)


@pytest.mark.parametrize("transport", ["sse", "http"])
def test_mcp_server_config_accepts_transport_alias(transport: str):
    """The MCP-spec ``transport`` field should be accepted as an alias for ``type``.

    Regression test for https://github.com/bytedance/deer-flow/issues/3238 — a
    remote MCP server configured with only ``transport: sse`` was previously
    misidentified as ``stdio`` (the default for ``type``).
    """
    config = McpServerConfig.model_validate(
        {
            "transport": transport,
            "url": "https://example.com/mcp",
        }
    )

    assert config.type == transport

    params = build_server_params("aliased-server", config)
    assert params["transport"] == transport
    assert params["url"] == "https://example.com/mcp"


def test_mcp_server_config_type_takes_precedence_over_transport():
    """When both ``type`` and ``transport`` are provided, ``type`` wins."""
    config = McpServerConfig.model_validate(
        {
            "type": "http",
            "transport": "sse",
            "url": "https://example.com/mcp",
        }
    )

    assert config.type == "http"


def test_build_servers_config_returns_empty_when_no_enabled_servers():
    extensions = ExtensionsConfig(
        mcp_servers={
            "disabled-a": McpServerConfig(enabled=False, type="stdio", command="echo"),
            "disabled-b": McpServerConfig(enabled=False, type="http", url="https://example.com"),
        },
        skills={},
    )

    assert build_servers_config(extensions) == {}


def test_build_servers_config_skips_invalid_server_and_keeps_valid_ones():
    extensions = ExtensionsConfig(
        mcp_servers={
            "valid-stdio": McpServerConfig(enabled=True, type="stdio", command="npx", args=["server"]),
            "invalid-stdio": McpServerConfig(enabled=True, type="stdio", command=None),
            "disabled-http": McpServerConfig(enabled=False, type="http", url="https://disabled.example.com"),
        },
        skills={},
    )

    result = build_servers_config(extensions)

    assert "valid-stdio" in result
    assert result["valid-stdio"]["transport"] == "stdio"
    assert "invalid-stdio" not in result
    assert "disabled-http" not in result
