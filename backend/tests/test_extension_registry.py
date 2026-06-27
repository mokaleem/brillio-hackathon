from pathlib import Path

import pytest
from pydantic import ValidationError

from deerflow.extensions import ExtensionKind, ExtensionManifest, ExtensionSource


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
