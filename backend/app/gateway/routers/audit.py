from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.gateway.deps import require_admin_user
from deerflow.audit import audit_log_path

_ADMIN_REQUIRED_DETAIL = "Admin privileges required to inspect execution audit records."

router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditExecutionRecord(BaseModel):
    event: str = "extension.execution"
    started_at: str
    ended_at: str | None = None
    duration_ms: int | None = None
    status: str
    extension: dict[str, Any] = Field(default_factory=dict)
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None


class AuditExecutionsResponse(BaseModel):
    records: list[AuditExecutionRecord]
    count: int
    path: str


class AuditEvidenceSummary(BaseModel):
    total_records: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    extension_counts: dict[str, int] = Field(default_factory=dict)
    artifact_count: int = 0


class AuditEvidenceExport(BaseModel):
    schema_version: int = 1
    generated_at: str
    source_path: str
    summary: AuditEvidenceSummary
    records: list[AuditExecutionRecord]


@router.get("/executions", response_model=AuditExecutionsResponse)
async def list_audit_executions(
    request: Request,
    limit: int = Query(default=25, ge=1, le=200),
) -> AuditExecutionsResponse:
    await require_admin_user(request, detail=_ADMIN_REQUIRED_DETAIL)
    path = audit_log_path()
    records = _read_recent_execution_records(path, limit=limit)
    return AuditExecutionsResponse(
        records=records,
        count=len(records),
        path=str(path),
    )


@router.get("/evidence", response_model=AuditEvidenceExport)
async def export_audit_evidence(
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
) -> JSONResponse:
    await require_admin_user(request, detail=_ADMIN_REQUIRED_DETAIL)
    path = audit_log_path()
    records = list(reversed(_read_recent_execution_records(path, limit=limit)))
    evidence = _build_evidence_export(path, records)
    return JSONResponse(
        content=evidence.model_dump(mode="json"),
        headers={"Content-Disposition": 'attachment; filename="deerflow-audit-evidence.json"'},
    )


def _read_recent_execution_records(path: Path, *, limit: int) -> list[AuditExecutionRecord]:
    if not path.is_file():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    records: list[AuditExecutionRecord] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            records.append(AuditExecutionRecord.model_validate(payload))
        except (json.JSONDecodeError, ValueError):
            continue
        if len(records) >= limit:
            break
    return records


def _build_evidence_export(path: Path, records: list[AuditExecutionRecord]) -> AuditEvidenceExport:
    status_counts = Counter(record.status for record in records)
    extension_counts = Counter(str(record.extension.get("name") or "unknown") for record in records)
    return AuditEvidenceExport(
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        source_path=str(path),
        summary=AuditEvidenceSummary(
            total_records=len(records),
            status_counts=dict(sorted(status_counts.items())),
            extension_counts=dict(sorted(extension_counts.items())),
            artifact_count=sum(len(record.artifacts) for record in records),
        ),
        records=records,
    )
