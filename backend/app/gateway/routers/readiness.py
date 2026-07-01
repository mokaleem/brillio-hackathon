from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.gateway.auth_disabled import (
    is_auth_disabled,
    is_auth_disabled_requested,
    is_explicit_production_environment,
)
from app.gateway.config import get_gateway_config
from app.gateway.deps import require_admin_user
from deerflow.config.paths import Paths
from deerflow.config.tracing_config import get_tracing_config
from deerflow.extensions.policy import (
    RUNTIME_RISK_ENV_VAR,
    ExtensionPermissionError,
    ExtensionRuntimePolicy,
)

_ADMIN_REQUIRED_DETAIL = "Admin privileges required to inspect enterprise readiness."
_MODEL_CREDENTIAL_ENV_VARS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "AZURE_OPENAI_API_KEY",
)

router = APIRouter(prefix="/api/readiness", tags=["readiness"])

ComponentStatus = Literal["ok", "warning", "error"]
OverallStatus = Literal["ready", "degraded", "not_ready"]


class ReadinessComponent(BaseModel):
    name: str
    status: ComponentStatus
    detail: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnterpriseReadinessResponse(BaseModel):
    status: OverallStatus
    generated_at: str
    components: list[ReadinessComponent]


@router.get("", response_model=EnterpriseReadinessResponse)
async def enterprise_readiness(request: Request) -> EnterpriseReadinessResponse:
    await require_admin_user(request, detail=_ADMIN_REQUIRED_DETAIL)
    components = build_readiness_components()
    return EnterpriseReadinessResponse(
        status=_overall_status(components),
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        components=components,
    )


def build_readiness_components() -> list[ReadinessComponent]:
    return [
        _auth_status(),
        _model_credentials_status(),
        _tracing_status(),
        _registry_policy_status(),
        _artifact_storage_status(),
        _api_docs_status(),
    ]


def _overall_status(components: list[ReadinessComponent]) -> OverallStatus:
    statuses = {component.status for component in components}
    if "error" in statuses:
        return "not_ready"
    if "warning" in statuses:
        return "degraded"
    return "ready"


def _auth_status() -> ReadinessComponent:
    if is_auth_disabled():
        return ReadinessComponent(
            name="auth",
            status="error",
            detail="Authentication is disabled for this gateway process.",
            metadata={"env_var": "DEER_FLOW_AUTH_DISABLED"},
        )
    if is_auth_disabled_requested() and is_explicit_production_environment():
        return ReadinessComponent(
            name="auth",
            status="warning",
            detail="Authentication disablement was requested but blocked by production environment guardrails.",
            metadata={"env_var": "DEER_FLOW_AUTH_DISABLED"},
        )
    return ReadinessComponent(
        name="auth",
        status="ok",
        detail="Authentication middleware is expected to enforce sessions.",
    )


def _model_credentials_status() -> ReadinessComponent:
    configured = [name for name in _MODEL_CREDENTIAL_ENV_VARS if os.environ.get(name)]
    if configured:
        return ReadinessComponent(
            name="model_credentials",
            status="ok",
            detail="At least one model credential is configured.",
            metadata={"configured": configured},
        )
    return ReadinessComponent(
        name="model_credentials",
        status="error",
        detail="No model credential environment variables are configured.",
        metadata={"accepted_env_vars": list(_MODEL_CREDENTIAL_ENV_VARS)},
    )


def _tracing_status() -> ReadinessComponent:
    config = get_tracing_config()
    try:
        config.validate_enabled()
    except ValueError as exc:
        return ReadinessComponent(
            name="tracing",
            status="error",
            detail=str(exc),
            metadata={"explicitly_enabled": config.explicitly_enabled_providers},
        )

    configured = config.enabled_providers
    if configured:
        return ReadinessComponent(
            name="tracing",
            status="ok",
            detail="Tracing is configured.",
            metadata={"providers": configured},
        )
    return ReadinessComponent(
        name="tracing",
        status="warning",
        detail="No tracing provider is enabled.",
        metadata={"explicitly_enabled": config.explicitly_enabled_providers},
    )


def _registry_policy_status() -> ReadinessComponent:
    try:
        policy = ExtensionRuntimePolicy.from_environment()
    except (ExtensionPermissionError, ValueError) as exc:
        return ReadinessComponent(
            name="registry_policy",
            status="error",
            detail=str(exc),
            metadata={"env_var": RUNTIME_RISK_ENV_VAR},
        )
    allowed = sorted(policy.allowed_risk_levels)
    if "high" in allowed:
        return ReadinessComponent(
            name="registry_policy",
            status="warning",
            detail="High-risk extensions are allowed by runtime policy.",
            metadata={"allowed_risk_levels": allowed, "env_var": RUNTIME_RISK_ENV_VAR},
        )
    return ReadinessComponent(
        name="registry_policy",
        status="ok",
        detail="Runtime extension policy blocks high-risk extensions by default.",
        metadata={"allowed_risk_levels": allowed, "env_var": RUNTIME_RISK_ENV_VAR},
    )


def _artifact_storage_status() -> ReadinessComponent:
    paths = Paths()
    base_dir = paths.base_dir
    host_base_dir = paths.host_base_dir
    try:
        _assert_writable_directory(base_dir)
    except OSError as exc:
        return ReadinessComponent(
            name="artifact_storage",
            status="error",
            detail=f"Artifact base directory is not writable: {exc}",
            metadata={"base_dir": str(base_dir), "host_base_dir": str(host_base_dir)},
        )

    if os.environ.get("DEER_FLOW_HOST_BASE_DIR") and not host_base_dir.exists():
        return ReadinessComponent(
            name="artifact_storage",
            status="warning",
            detail="Host artifact base directory is configured but does not exist from this process.",
            metadata={"base_dir": str(base_dir), "host_base_dir": str(host_base_dir)},
        )

    return ReadinessComponent(
        name="artifact_storage",
        status="ok",
        detail="Artifact base directory is writable.",
        metadata={"base_dir": str(base_dir), "host_base_dir": str(host_base_dir)},
    )


def _api_docs_status() -> ReadinessComponent:
    if get_gateway_config().enable_docs:
        return ReadinessComponent(
            name="api_docs",
            status="warning",
            detail="Swagger/ReDoc/OpenAPI endpoints are enabled.",
            metadata={"env_var": "GATEWAY_ENABLE_DOCS"},
        )
    return ReadinessComponent(
        name="api_docs",
        status="ok",
        detail="Swagger/ReDoc/OpenAPI endpoints are disabled.",
        metadata={"env_var": "GATEWAY_ENABLE_DOCS"},
    )


def _assert_writable_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=path):
        pass
