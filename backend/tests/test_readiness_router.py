from pathlib import Path

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway import config as gateway_config
from app.gateway.auth.models import User
from app.gateway.routers import readiness
from deerflow.config.tracing_config import reset_tracing_config


@pytest.fixture(autouse=True)
def _reset_cached_readiness_config():
    reset_tracing_config()
    gateway_config._gateway_config = None
    try:
        yield
    finally:
        reset_tracing_config()
        gateway_config._gateway_config = None


def _make_app() -> FastAPI:
    app = make_authed_test_app()
    app.include_router(readiness.router)
    return app


def _make_admin_app() -> FastAPI:
    def _admin_user() -> User:
        return User(email="admin@example.com", password_hash="x", system_role="admin")

    app = make_authed_test_app(user_factory=_admin_user)
    app.include_router(readiness.router)
    return app


def _reset_cached_env_config(monkeypatch) -> None:
    monkeypatch.setattr(gateway_config, "_gateway_config", None)
    reset_tracing_config()


def test_readiness_requires_admin_user() -> None:
    with TestClient(_make_app()) as client:
        response = client.get("/api/readiness")

    assert response.status_code == 403
    assert "Admin privileges" in response.json()["detail"]


def test_readiness_reports_operator_status(monkeypatch, tmp_path: Path) -> None:
    _reset_cached_env_config(monkeypatch)
    monkeypatch.setenv("DEER_FLOW_HOME", str(tmp_path / "deer-home"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-model-credential")
    monkeypatch.setenv("GATEWAY_ENABLE_DOCS", "false")
    monkeypatch.delenv("DEER_FLOW_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("LANGFUSE_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS", raising=False)

    with TestClient(_make_admin_app()) as client:
        response = client.get("/api/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    components = {component["name"]: component for component in payload["components"]}
    assert set(components) == {
        "auth",
        "model_credentials",
        "tracing",
        "registry_policy",
        "artifact_storage",
        "api_docs",
    }
    assert components["auth"]["status"] == "ok"
    assert components["model_credentials"]["status"] == "ok"
    assert components["tracing"]["status"] == "warning"
    assert components["registry_policy"]["metadata"]["allowed_risk_levels"] == ["low", "medium"]
    assert components["artifact_storage"]["status"] == "ok"
    assert components["api_docs"]["status"] == "ok"


def test_readiness_reports_enterprise_misconfiguration(monkeypatch, tmp_path: Path) -> None:
    _reset_cached_env_config(monkeypatch)
    monkeypatch.setenv("DEER_FLOW_HOME", str(tmp_path / "deer-home"))
    monkeypatch.setenv("DEER_FLOW_AUTH_DISABLED", "1")
    monkeypatch.setenv("GATEWAY_ENABLE_DOCS", "true")
    monkeypatch.setenv("LANGFUSE_TRACING", "true")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setenv("DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS", "critical")
    for name in readiness._MODEL_CREDENTIAL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    with TestClient(_make_admin_app()) as client:
        response = client.get("/api/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_ready"
    components = {component["name"]: component for component in payload["components"]}
    assert components["auth"]["status"] == "error"
    assert components["model_credentials"]["status"] == "error"
    assert components["tracing"]["status"] == "error"
    assert components["registry_policy"]["status"] == "error"
    assert components["api_docs"]["status"] == "warning"


def test_readiness_errors_when_high_risk_approval_gate_is_disabled(monkeypatch, tmp_path: Path) -> None:
    _reset_cached_env_config(monkeypatch)
    monkeypatch.setenv("DEER_FLOW_HOME", str(tmp_path / "deer-home"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-model-credential")
    monkeypatch.setenv("GATEWAY_ENABLE_DOCS", "false")
    monkeypatch.setenv("DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS", "low,medium,high")
    monkeypatch.setenv("DEERFLOW_EXTENSION_REQUIRE_HIGH_RISK_APPROVAL", "false")

    with TestClient(_make_admin_app()) as client:
        response = client.get("/api/readiness")

    assert response.status_code == 200
    payload = response.json()
    components = {component["name"]: component for component in payload["components"]}
    assert payload["status"] == "not_ready"
    assert components["registry_policy"]["status"] == "error"
    assert components["registry_policy"]["metadata"]["require_high_risk_approval"] is False
