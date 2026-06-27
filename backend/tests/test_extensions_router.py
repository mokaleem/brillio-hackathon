from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.routers import extensions


def _make_app() -> FastAPI:
    app = FastAPI()
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
