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
    assert [extension["name"] for extension in payload["extensions"] if extension["kind"] == "tool"] == ["html-report", "csv-export"]
    assert payload["count"] == 3


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
