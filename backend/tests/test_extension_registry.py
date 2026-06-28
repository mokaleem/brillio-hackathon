import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from deerflow.config.extensions_config import McpServerConfig
from deerflow.config.tool_config import ToolConfig
from deerflow.extensions import (
    ExtensionKind,
    ExtensionManifest,
    ExtensionSource,
    execute_python_entrypoint,
    get_runtime_extension_manifest_paths,
    load_extension_catalog,
    load_extension_manifest,
    load_runtime_extension_catalog,
    materialize_agent_factory,
    materialize_mcp_server_config,
    materialize_skill_path,
    materialize_tool,
    materialize_tool_config,
)


def test_manifest_parses_minimal_tool_descriptor() -> None:
    manifest = ExtensionManifest.model_validate(
        {
            "version": 1,
            "extensions": [
                {
                    "kind": "tool",
                    "name": "html-report",
                    "enabled": True,
                    "source": "local",
                    "entrypoint": "internal_tools.reporting:html_report_tool",
                    "description": "Generate HTML reports",
                }
            ],
        }
    )

    extension = manifest.extensions[0]
    assert extension.kind is ExtensionKind.TOOL
    assert extension.source is ExtensionSource.LOCAL
    assert extension.name == "html-report"
    assert extension.entrypoint == "internal_tools.reporting:html_report_tool"
    assert extension.description == "Generate HTML reports"


def test_descriptor_rejects_invalid_name() -> None:
    with pytest.raises(ValidationError, match="hyphen-case"):
        ExtensionManifest.model_validate(
            {
                "version": 1,
                "extensions": [
                    {
                        "kind": "tool",
                        "name": "Bad Name",
                        "source": "local",
                        "entrypoint": "internal_tools.reporting:html_report_tool",
                    }
                ],
            }
        )


def test_import_resolves_relative_path_under_repo_root(tmp_path: Path) -> None:
    manifest = ExtensionManifest.model_validate(
        {
            "version": 1,
            "imports": [
                {
                    "name": "internal-tools",
                    "kind": "tool",
                    "type": "directory",
                    "path": "internal_tools",
                }
            ],
        }
    )

    resolved = manifest.imports[0].resolve_path(tmp_path)
    assert resolved == tmp_path / "internal_tools"


def test_import_rejects_path_escape(tmp_path: Path) -> None:
    manifest = ExtensionManifest.model_validate(
        {
            "version": 1,
            "imports": [
                {
                    "name": "bad-import",
                    "kind": "tool",
                    "type": "directory",
                    "path": "../outside",
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="within the repository"):
        manifest.imports[0].resolve_path(tmp_path)


def test_load_extension_manifest_from_json(tmp_path: Path) -> None:
    manifest_path = tmp_path / "extensions.json"
    manifest_path.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "skill",
              "name": "market-research",
              "enabled": true,
              "source": "local",
              "entrypoint": "internal_skills/market-research",
              "description": "Research market context"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    manifest = load_extension_manifest(manifest_path)

    assert manifest.extensions[0].kind is ExtensionKind.SKILL
    assert manifest.extensions[0].name == "market-research"


def test_load_extension_manifest_missing_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_extension_manifest(tmp_path / "missing.json")


def test_catalog_filters_enabled_extensions(tmp_path: Path) -> None:
    manifest_path = tmp_path / "extensions.json"
    manifest_path.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "tool",
              "name": "html-report",
              "enabled": true,
              "source": "local",
              "entrypoint": "internal_tools.reporting:html_report_tool"
            },
            {
              "kind": "tool",
              "name": "disabled-tool",
              "enabled": false,
              "source": "local",
              "entrypoint": "internal_tools.disabled:tool"
            },
            {
              "kind": "agent",
              "name": "finance-agent",
              "enabled": true,
              "source": "local",
              "entrypoint": "internal_agents.finance:create_agent"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    catalog = load_extension_catalog([manifest_path], repo_root=tmp_path)

    assert [extension.name for extension in catalog.enabled(kind="tool")] == ["html-report"]
    assert [extension.name for extension in catalog.enabled(kind="agent")] == ["finance-agent"]


def test_catalog_rejects_duplicate_kind_and_name(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    manifest = """
    {
      "version": 1,
      "extensions": [
        {
          "kind": "tool",
          "name": "html-report",
          "enabled": true,
          "source": "local",
          "entrypoint": "internal_tools.reporting:html_report_tool"
        }
      ]
    }
    """
    first.write_text(manifest, encoding="utf-8")
    second.write_text(manifest, encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate extension"):
        load_extension_catalog([first, second], repo_root=tmp_path)


def test_runtime_catalog_uses_env_manifest(monkeypatch, tmp_path: Path) -> None:
    manifest_path = tmp_path / "extensions.json"
    manifest_path.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "tool",
              "name": "company-metric-tool",
              "enabled": true,
              "source": "local",
              "entrypoint": "tests.support.registry_tools:company_metric_tool"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(manifest_path))

    paths = get_runtime_extension_manifest_paths(repo_root=tmp_path)
    catalog = load_runtime_extension_catalog(repo_root=tmp_path)

    assert paths == [manifest_path]
    assert [extension.name for extension in catalog.enabled(kind="tool")] == ["company-metric-tool"]


def test_runtime_catalog_resolves_relative_env_manifest_against_project_root(monkeypatch, tmp_path: Path) -> None:
    manifest_path = tmp_path / "registries" / "extensions.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "tool",
              "name": "company-metric-tool",
              "enabled": true,
              "source": "local",
              "entrypoint": "tests.support.registry_tools:company_metric_tool"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", "registries/extensions.json")

    paths = get_runtime_extension_manifest_paths(repo_root=tmp_path)

    assert paths == [manifest_path]


def test_runtime_catalog_adds_project_root_to_python_path(monkeypatch, tmp_path: Path) -> None:
    package_dir = tmp_path / "company_tools"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "demo.py").write_text("def make_value():\n    return 'loaded'\n", encoding="utf-8")
    manifest_path = tmp_path / "registries" / "extensions.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "agent",
              "name": "demo-agent",
              "enabled": true,
              "source": "local",
              "entrypoint": "company_tools.demo:make_value"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(manifest_path))
    root_text = str(tmp_path.resolve(strict=False))
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry != root_text])

    catalog = load_runtime_extension_catalog(repo_root=tmp_path)
    factory = materialize_agent_factory(catalog.enabled(kind="agent")[0])

    assert factory() == "loaded"
    assert sys.path[0] == root_text


def test_runtime_catalog_is_empty_without_default_manifest(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DEERFLOW_EXTENSION_MANIFESTS", raising=False)

    catalog = load_runtime_extension_catalog(repo_root=tmp_path)

    assert catalog.extensions == ()
    assert catalog.repo_root == tmp_path.resolve()


def test_example_internal_extensions_manifest_loads() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "registries" / "internal_extensions.example.json"

    catalog = load_extension_catalog([manifest_path], repo_root=repo_root)

    assert [extension.name for extension in catalog.enabled(kind="agent")] == ["reporting-agent"]
    assert [extension.name for extension in catalog.enabled(kind="tool")] == ["html-report", "csv-export", "pdf-report"]
    assert catalog.enabled(kind="skill") == []


def test_example_internal_extensions_manifest_materializes_reporting_tools(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(repo_root))
    manifest_path = repo_root / "registries" / "internal_extensions.example.json"

    catalog = load_extension_catalog([manifest_path], repo_root=repo_root)
    tools = [materialize_tool(extension) for extension in catalog.enabled(kind="tool")]

    assert [tool.name for tool in tools] == ["html_report", "csv_export", "pdf_report"]


def test_execute_python_entrypoint_calls_importable_function() -> None:
    assert execute_python_entrypoint("math:sqrt", 81) == 9


def test_execute_python_entrypoint_rejects_malformed_entrypoint() -> None:
    with pytest.raises(ValueError, match="module:function"):
        execute_python_entrypoint("math.sqrt")


def test_materialize_tool_returns_base_tool() -> None:
    extension = ExtensionManifest.model_validate(
        {
            "version": 1,
            "extensions": [
                {
                    "kind": "tool",
                    "name": "ask-clarification",
                    "enabled": True,
                    "source": "local",
                    "entrypoint": "deerflow.tools.builtins.clarification_tool:ask_clarification_tool",
                    "description": "Double a value",
                }
            ],
        }
    ).extensions[0]

    tool = materialize_tool(extension)

    assert tool.name == "ask_clarification"


def test_materialize_tool_config_uses_descriptor_metadata_group() -> None:
    extension = ExtensionManifest.model_validate(
        {
            "version": 1,
            "extensions": [
                {
                    "kind": "tool",
                    "name": "demo-registry-tool",
                    "enabled": True,
                    "source": "local",
                    "entrypoint": "deerflow.tools.builtins.clarification_tool:ask_clarification_tool",
                    "metadata": {"group": "reporting"},
                }
            ],
        }
    ).extensions[0]

    config = materialize_tool_config(extension)

    assert isinstance(config, ToolConfig)
    assert config.name == "demo-registry-tool"
    assert config.group == "reporting"
    assert config.use == "deerflow.tools.builtins.clarification_tool:ask_clarification_tool"


def test_materialize_mcp_server_config_from_metadata() -> None:
    extension = ExtensionManifest.model_validate(
        {
            "version": 1,
            "extensions": [
                {
                    "kind": "mcp",
                    "name": "local-docs",
                    "enabled": True,
                    "source": "local",
                    "description": "Local docs MCP",
                    "metadata": {
                        "type": "stdio",
                        "command": "python",
                        "args": ["-m", "internal_mcps.docs"],
                        "env": {"DOCS_ROOT": "$DOCS_ROOT"},
                    },
                }
            ],
        }
    ).extensions[0]

    config = materialize_mcp_server_config(extension)

    assert isinstance(config, McpServerConfig)
    assert config.enabled is True
    assert config.command == "python"
    assert config.args == ["-m", "internal_mcps.docs"]
    assert config.description == "Local docs MCP"


def test_materialize_skill_path_stays_inside_repo(tmp_path: Path) -> None:
    skill_dir = tmp_path / "internal_skills" / "market-research"
    skill_dir.mkdir(parents=True)
    extension = ExtensionManifest.model_validate(
        {
            "version": 1,
            "extensions": [
                {
                    "kind": "skill",
                    "name": "market-research",
                    "enabled": True,
                    "source": "local",
                    "entrypoint": "internal_skills/market-research",
                }
            ],
        }
    ).extensions[0]

    assert materialize_skill_path(extension, repo_root=tmp_path) == skill_dir


def test_materialize_agent_factory_returns_callable() -> None:
    extension = ExtensionManifest.model_validate(
        {
            "version": 1,
            "extensions": [
                {
                    "kind": "agent",
                    "name": "demo-agent",
                    "enabled": True,
                    "source": "local",
                    "entrypoint": "math:sqrt",
                }
            ],
        }
    ).extensions[0]

    factory = materialize_agent_factory(extension)

    assert factory(81) == 9
