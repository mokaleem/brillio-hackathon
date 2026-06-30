from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from _router_auth_helpers import make_authed_test_app
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.auth.models import User
from app.gateway.routers import audit


def _make_admin_app() -> FastAPI:
    def _admin_user() -> User:
        return User(email="admin@example.com", password_hash="x", system_role="admin")

    app = make_authed_test_app(user_factory=_admin_user)
    app.include_router(audit.router)
    return app


def test_audit_executions_returns_recent_records(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "audit" / "executions.jsonl"
    log_path.parent.mkdir()
    records = [
        _record("tool", "html-report", "success", "2026-06-29T10:00:00Z"),
        _record("tool", "python-function", "error", "2026-06-29T10:01:00Z"),
    ]
    log_path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    monkeypatch.setenv("DEER_FLOW_AUDIT_LOG_PATH", str(log_path))

    with TestClient(_make_admin_app()) as client:
        response = client.get("/api/audit/executions?limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["path"] == str(log_path.resolve())
    assert payload["records"][0]["extension"]["name"] == "python-function"
    assert payload["records"][0]["status"] == "error"


def test_audit_executions_returns_empty_for_missing_log(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEER_FLOW_AUDIT_LOG_PATH", str(tmp_path / "missing.jsonl"))

    with TestClient(_make_admin_app()) as client:
        response = client.get("/api/audit/executions")

    assert response.status_code == 200
    assert response.json()["records"] == []


def _record(kind: str, name: str, status: str, started_at: str) -> dict:
    return {
        "event": "extension.execution",
        "started_at": started_at,
        "ended_at": datetime.now(UTC).isoformat(),
        "duration_ms": 12,
        "status": status,
        "extension": {
            "kind": kind,
            "name": name,
            "source": "registry",
            "risk_level": "medium",
            "provenance": {"source_name": "demo-registry"},
        },
        "input_summary": {"type": "mapping", "keys": ["title"]},
        "output_summary": {"type": "string", "length": 42},
        "artifacts": ["reports/demo.html"],
        "error": {"type": "RuntimeError", "message": "boom"} if status == "error" else None,
    }
