from pathlib import Path

import pytest
from pydantic import ValidationError

from deerflow.extensions import ExtensionKind, ExtensionManifest, ExtensionSource, execute_python_entrypoint, load_extension_catalog, load_extension_manifest


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


def test_example_internal_extensions_manifest_loads() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "registries" / "internal_extensions.example.json"

    catalog = load_extension_catalog([manifest_path], repo_root=repo_root)

    assert [extension.name for extension in catalog.enabled(kind="tool")] == ["html-report", "csv-export"]
    assert catalog.enabled(kind="skill") == []


def test_execute_python_entrypoint_calls_importable_function() -> None:
    assert execute_python_entrypoint("math:sqrt", 81) == 9


def test_execute_python_entrypoint_rejects_malformed_entrypoint() -> None:
    with pytest.raises(ValueError, match="module:function"):
        execute_python_entrypoint("math.sqrt")
