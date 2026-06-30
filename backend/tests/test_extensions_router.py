from pathlib import Path

from _router_auth_helpers import make_authed_test_app
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.auth.models import User
from app.gateway.routers import extensions


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(extensions.router)
    return app


def _make_admin_app() -> FastAPI:
    def _admin_user() -> User:
        return User(email="admin@example.com", password_hash="x", system_role="admin")

    app = make_authed_test_app(user_factory=_admin_user)
    app.include_router(extensions.router)
    return app


def test_extensions_router_lists_default_manifest() -> None:
    with TestClient(_make_app()) as client:
        response = client.get("/api/extensions")

    assert response.status_code == 200
    payload = response.json()
    assert [extension["name"] for extension in payload["extensions"] if extension["kind"] == "tool"] == [
        "html-report",
        "csv-export",
        "pdf-report",
        "python-function",
    ]
    assert payload["count"] == 7


def test_extensions_router_filters_by_kind() -> None:
    with TestClient(_make_app()) as client:
        response = client.get("/api/extensions?kind=skill")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["extensions"][0]["name"] == "market-research"


def test_extensions_router_uses_env_manifest(monkeypatch, tmp_path: Path) -> None:
    manifest_path = tmp_path / "extensions.json"
    manifest_path.write_text(
        """
        {
          "version": 1,
          "extensions": [
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
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(manifest_path))

    with TestClient(_make_app()) as client:
        response = client.get("/api/extensions")

    assert response.status_code == 200
    assert response.json()["extensions"][0]["name"] == "finance-agent"


def test_extensions_router_resolves_relative_env_manifest(monkeypatch, tmp_path: Path) -> None:
    manifest_path = tmp_path / "registries" / "extensions.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        """
        {
          "version": 1,
          "extensions": [
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
    monkeypatch.setattr(extensions, "_repo_root", lambda: tmp_path)
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", "registries/extensions.json")

    with TestClient(_make_app()) as client:
        response = client.get("/api/extensions")

    assert response.status_code == 200
    assert response.json()["extensions"][0]["name"] == "finance-agent"


def test_extensions_validate_reports_descriptor_errors(monkeypatch, tmp_path: Path) -> None:
    manifest_path = tmp_path / "bad.json"
    manifest_path.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "tool",
              "name": "Bad Name",
              "source": "local",
              "entrypoint": "internal_tools.bad:tool"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(manifest_path))

    with TestClient(_make_admin_app()) as client:
        response = client.post("/api/extensions/validate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["count"] == 0
    assert "hyphen-case" in payload["errors"][0]


def test_extensions_health_reports_import_and_mcp_errors(monkeypatch, tmp_path: Path) -> None:
    manifest_path = tmp_path / "extensions.json"
    manifest_path.write_text(
        """
        {
          "version": 1,
          "imports": [
            {
              "name": "missing-tools",
              "kind": "tool",
              "type": "directory",
              "path": "missing_tools"
            }
          ],
          "extensions": [
            {
              "kind": "mcp",
              "name": "bad-mcp",
              "enabled": true,
              "source": "local",
              "metadata": {
                "type": "stdio"
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(manifest_path))

    with TestClient(_make_admin_app()) as client:
        response = client.get("/api/extensions/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["count"] == 1
    assert str(manifest_path) in payload["manifests"]
    assert any("missing-tools" in error and "does not exist" in error for error in payload["errors"])
    assert any("bad-mcp" in error and "metadata.command" in error for error in payload["errors"])


def test_extensions_reload_returns_active_catalog(monkeypatch, tmp_path: Path) -> None:
    manifest_path = tmp_path / "extensions.json"
    manifest_path.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "tool",
              "name": "csv-export",
              "enabled": true,
              "source": "local",
              "entrypoint": "internal_tools.reporting:csv_export_tool"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(manifest_path))

    with TestClient(_make_admin_app()) as client:
        response = client.post("/api/extensions/reload")

    assert response.status_code == 200
    assert response.json()["extensions"][0]["name"] == "csv-export"


def test_extensions_update_enabled_writes_manifest(monkeypatch, tmp_path: Path) -> None:
    manifest_path = tmp_path / "extensions.json"
    manifest_path.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "skill",
              "name": "market-research",
              "enabled": false,
              "source": "local",
              "entrypoint": "internal_skills/market-research"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(manifest_path))

    with TestClient(_make_admin_app()) as client:
        response = client.put("/api/extensions/skill/market-research", json={"enabled": True})

    assert response.status_code == 200
    assert response.json()["extension"]["enabled"] is True

    with TestClient(_make_app()) as client:
        list_response = client.get("/api/extensions?kind=skill")
    assert list_response.json()["extensions"][0]["enabled"] is True


def test_extensions_import_preview_returns_external_manifest(monkeypatch, tmp_path: Path) -> None:
    base_manifest = tmp_path / "registries" / "internal_extensions.example.json"
    base_manifest.parent.mkdir()
    base_manifest.write_text('{"version": 1, "extensions": []}', encoding="utf-8")
    monkeypatch.setattr(extensions, "_repo_root", lambda: tmp_path)
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(base_manifest))

    manifest_json = """
    {
      "version": 1,
      "metadata": {
        "registry": "forecast-demo",
        "url": "https://registry.example.com/forecast.json"
      },
      "extensions": [
        {
          "kind": "tool",
          "name": "forecast-export",
          "enabled": false,
          "source": "registry",
          "entrypoint": "company_tools.forecast:export"
        }
      ]
    }
    """

    with TestClient(_make_admin_app()) as client:
        response = client.post("/api/extensions/import/preview", json={"manifest_json": manifest_json})

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["count"] == 1
    assert payload["extensions"][0]["name"] == "forecast-export"
    assert payload["changes"] == [
        {
            "key": "tool:forecast-export",
            "action": "add",
            "extension": payload["extensions"][0],
            "existing": None,
            "reason": None,
        }
    ]
    assert any("tool:forecast-export comes from source 'registry'" in warning for warning in payload["warnings"])
    assert any("tool:forecast-export does not declare a risk_level" in warning for warning in payload["warnings"])


def test_extensions_import_preview_rejects_oversized_manifest(monkeypatch, tmp_path: Path) -> None:
    base_manifest = tmp_path / "registries" / "internal_extensions.example.json"
    base_manifest.parent.mkdir()
    base_manifest.write_text('{"version": 1, "extensions": []}', encoding="utf-8")
    monkeypatch.setattr(extensions, "_repo_root", lambda: tmp_path)
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(base_manifest))
    monkeypatch.setenv("DEERFLOW_EXTENSION_IMPORT_MAX_BYTES", "64")

    manifest_json = '{"version": 1, "extensions": [], "metadata": {"padding": "' + ("x" * 128) + '"}}'

    with TestClient(_make_admin_app()) as client:
        response = client.post("/api/extensions/import/preview", json={"manifest_json": manifest_json})

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert "too large" in payload["errors"][0]


def test_extensions_import_preview_rejects_too_many_descriptors(monkeypatch, tmp_path: Path) -> None:
    base_manifest = tmp_path / "registries" / "internal_extensions.example.json"
    base_manifest.parent.mkdir()
    base_manifest.write_text('{"version": 1, "extensions": []}', encoding="utf-8")
    monkeypatch.setattr(extensions, "_repo_root", lambda: tmp_path)
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(base_manifest))
    monkeypatch.setenv("DEERFLOW_EXTENSION_IMPORT_MAX_EXTENSIONS", "1")

    manifest_json = """
    {
      "version": 1,
      "metadata": {
        "registry": "forecast-demo",
        "url": "https://registry.example.com/forecast.json"
      },
      "extensions": [
        {
          "kind": "tool",
          "name": "first-tool",
          "source": "registry",
          "entrypoint": "company_tools.first:tool"
        },
        {
          "kind": "tool",
          "name": "second-tool",
          "source": "registry",
          "entrypoint": "company_tools.second:tool"
        }
      ]
    }
    """

    with TestClient(_make_admin_app()) as client:
        response = client.post("/api/extensions/import/preview", json={"manifest_json": manifest_json})

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert "Limit is 1 extensions" in payload["errors"][0]


def test_extensions_import_preview_blocks_dangerous_entrypoints(monkeypatch, tmp_path: Path) -> None:
    base_manifest = tmp_path / "registries" / "internal_extensions.example.json"
    base_manifest.parent.mkdir()
    base_manifest.write_text('{"version": 1, "extensions": []}', encoding="utf-8")
    monkeypatch.setattr(extensions, "_repo_root", lambda: tmp_path)
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(base_manifest))

    manifest_json = """
    {
      "version": 1,
      "extensions": [
        {
          "kind": "tool",
          "name": "shell-tool",
          "enabled": true,
          "source": "registry",
          "entrypoint": "os:system",
          "risk_level": "high"
        }
      ]
    }
    """

    with TestClient(_make_admin_app()) as client:
        response = client.post("/api/extensions/import/preview", json={"manifest_json": manifest_json})

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert "not allowed by DEERFLOW_EXTENSION_IMPORT_ENTRYPOINT_PREFIXES" in payload["errors"][0]
    assert any("marked high risk" in warning for warning in payload["warnings"])


def test_extensions_import_preview_reports_duplicates(monkeypatch, tmp_path: Path) -> None:
    base_manifest = tmp_path / "registries" / "internal_extensions.example.json"
    base_manifest.parent.mkdir()
    base_manifest.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "tool",
              "name": "forecast-export",
              "enabled": true,
              "source": "local",
              "entrypoint": "company_tools.forecast:export"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(extensions, "_repo_root", lambda: tmp_path)
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(base_manifest))

    manifest_json = """
    {
      "version": 1,
      "extensions": [
        {
          "kind": "tool",
          "name": "forecast-export",
          "enabled": true,
          "source": "registry",
          "entrypoint": "company_tools.forecast:export"
        }
      ]
    }
    """

    with TestClient(_make_admin_app()) as client:
        response = client.post("/api/extensions/import/preview", json={"manifest_json": manifest_json})

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["duplicates"] == ["tool:forecast-export"]
    assert payload["changes"][0]["key"] == "tool:forecast-export"
    assert payload["changes"][0]["action"] == "conflict"
    assert payload["changes"][0]["existing"]["source"] == "local"
    assert payload["changes"][0]["reason"] == "Extension already exists in the active catalog."


def test_extensions_import_selected_descriptors(monkeypatch, tmp_path: Path) -> None:
    base_manifest = tmp_path / "registries" / "internal_extensions.example.json"
    base_manifest.parent.mkdir()
    base_manifest.write_text('{"version": 1, "extensions": []}', encoding="utf-8")
    monkeypatch.setattr(extensions, "_repo_root", lambda: tmp_path)
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(base_manifest))

    manifest_json = """
    {
      "version": 1,
      "metadata": {
        "registry": "forecast-demo",
        "url": "https://registry.example.com/forecast.json"
      },
      "extensions": [
        {
          "kind": "tool",
          "name": "forecast-export",
          "enabled": false,
          "source": "registry",
          "entrypoint": "company_tools.forecast:export"
        },
        {
          "kind": "skill",
          "name": "forecast-review",
          "enabled": false,
          "source": "registry",
          "entrypoint": "internal_skills/forecast-review"
        }
      ]
    }
    """

    with TestClient(_make_admin_app()) as client:
        response = client.post(
            "/api/extensions/import",
            json={"manifest_json": manifest_json, "selected": ["tool:forecast-export"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert [extension["name"] for extension in payload["extensions"]] == ["forecast-export"]
    assert payload["extensions"][0]["enabled"] is True
    provenance = payload["extensions"][0]["provenance"]
    assert provenance["registry_version"] == 1
    assert provenance["source_name"] == "forecast-demo"
    assert provenance["source_url"] == "https://registry.example.com/forecast.json"
    assert len(provenance["descriptor_hash"]) == 64
    assert provenance["imported_at"].endswith("Z")
    imported_manifest = tmp_path / "registries" / "imported_extensions.json"
    assert imported_manifest.exists()
    persisted = imported_manifest.read_text(encoding="utf-8")
    assert '"provenance"' in persisted
    assert provenance["descriptor_hash"] in persisted


def test_extensions_remove_imported_descriptor(monkeypatch, tmp_path: Path) -> None:
    base_manifest = tmp_path / "registries" / "internal_extensions.example.json"
    imported_manifest = tmp_path / "registries" / "imported_extensions.json"
    base_manifest.parent.mkdir()
    base_manifest.write_text('{"version": 1, "extensions": []}', encoding="utf-8")
    imported_manifest.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "tool",
              "name": "forecast-export",
              "enabled": true,
              "source": "registry",
              "entrypoint": "company_tools.forecast:export",
              "provenance": {
                "imported_at": "2026-06-29T16:00:00Z",
                "descriptor_hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                "registry_version": 1,
                "source_name": "forecast-demo"
              }
            },
            {
              "kind": "skill",
              "name": "forecast-review",
              "enabled": true,
              "source": "registry",
              "entrypoint": "internal_skills/forecast-review"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(extensions, "_repo_root", lambda: tmp_path)
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(base_manifest))

    with TestClient(_make_admin_app()) as client:
        response = client.delete("/api/extensions/imported/tool/forecast-export")

    assert response.status_code == 200
    payload = response.json()
    assert [extension["name"] for extension in payload["extensions"]] == ["forecast-review"]
    persisted = imported_manifest.read_text(encoding="utf-8")
    assert "forecast-export" not in persisted
    assert "forecast-review" in persisted


def test_extensions_remove_imported_descriptor_returns_404_for_base_manifest(monkeypatch, tmp_path: Path) -> None:
    base_manifest = tmp_path / "registries" / "internal_extensions.example.json"
    base_manifest.parent.mkdir()
    base_manifest.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "tool",
              "name": "html-report",
              "enabled": true,
              "source": "local",
              "entrypoint": "internal_tools.reporting:html_report"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(extensions, "_repo_root", lambda: tmp_path)
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(base_manifest))

    with TestClient(_make_admin_app()) as client:
        response = client.delete("/api/extensions/imported/tool/html-report")

    assert response.status_code == 404


def test_extensions_import_blocks_dangerous_selected_entrypoint(monkeypatch, tmp_path: Path) -> None:
    base_manifest = tmp_path / "registries" / "internal_extensions.example.json"
    base_manifest.parent.mkdir()
    base_manifest.write_text('{"version": 1, "extensions": []}', encoding="utf-8")
    monkeypatch.setattr(extensions, "_repo_root", lambda: tmp_path)
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", str(base_manifest))

    manifest_json = """
    {
      "version": 1,
      "extensions": [
        {
          "kind": "tool",
          "name": "shell-tool",
          "enabled": false,
          "source": "registry",
          "entrypoint": "os:system"
        }
      ]
    }
    """

    with TestClient(_make_admin_app()) as client:
        response = client.post(
            "/api/extensions/import",
            json={"manifest_json": manifest_json, "selected": ["tool:shell-tool"]},
        )

    assert response.status_code == 400
    assert "not allowed by DEERFLOW_EXTENSION_IMPORT_ENTRYPOINT_PREFIXES" in response.json()["detail"]
