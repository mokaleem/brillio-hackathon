from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ARTIFACT_PATTERN = re.compile(r"(?P<path>[^\s:]+\.(?:html|pdf|csv|md|json|txt))")
_MAX_KEYS = 12
_MAX_PREVIEW_CHARS = 160


def record_extension_execution(
    extension: Any,
    *,
    input_value: Any = None,
    output_value: Any = None,
    status: str,
    started_at: datetime,
    ended_at: datetime | None = None,
    error: BaseException | None = None,
) -> Path | None:
    if os.environ.get("DEER_FLOW_AUDIT_DISABLED", "").lower() in {"1", "true", "yes"}:
        return None

    ended = ended_at or datetime.now(UTC)
    record = {
        "event": "extension.execution",
        "started_at": _format_time(started_at),
        "ended_at": _format_time(ended),
        "duration_ms": max(0, int((ended - started_at).total_seconds() * 1000)),
        "status": status,
        "extension": {
            "kind": extension.kind.value,
            "name": extension.name,
            "display_name": extension.display_name,
            "source": extension.source.value,
            "entrypoint": extension.entrypoint,
            "risk_level": extension.risk_level,
            "owner": extension.owner,
            "provenance": extension.provenance.model_dump(mode="json") if extension.provenance else None,
        },
        "input_summary": summarize_value(input_value),
        "output_summary": summarize_value(output_value),
        "artifacts": extract_artifact_paths(output_value),
        "error": _summarize_error(error),
    }
    path = audit_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return path


def audit_log_path() -> Path:
    configured = os.environ.get("DEER_FLOW_AUDIT_LOG_PATH")
    if configured:
        return Path(configured).expanduser().resolve(strict=False)
    home = os.environ.get("DEER_FLOW_HOME")
    root = Path(home).expanduser() if home else Path.cwd() / ".deer-flow"
    return (root / "audit" / "executions.jsonl").resolve(strict=False)


def summarize_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "none"}
    if isinstance(value, Mapping):
        keys = [str(key) for key in value.keys()]
        return {
            "type": "mapping",
            "size": len(value),
            "keys": keys[:_MAX_KEYS],
            "truncated": len(keys) > _MAX_KEYS,
        }
    if isinstance(value, str):
        return {
            "type": "string",
            "length": len(value),
            "preview": value[:_MAX_PREVIEW_CHARS],
            "truncated": len(value) > _MAX_PREVIEW_CHARS,
        }
    if isinstance(value, list | tuple | set):
        return {"type": type(value).__name__, "size": len(value)}
    return {"type": type(value).__name__, "repr": repr(value)[:_MAX_PREVIEW_CHARS]}


def extract_artifact_paths(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Path):
        return [str(value)]
    if isinstance(value, Mapping):
        artifacts: list[str] = []
        for item in value.values():
            artifacts.extend(extract_artifact_paths(item))
        return sorted(set(artifacts))
    if isinstance(value, list | tuple | set):
        artifacts: list[str] = []
        for item in value:
            artifacts.extend(extract_artifact_paths(item))
        return sorted(set(artifacts))
    if isinstance(value, str):
        return sorted({match.group("path") for match in _ARTIFACT_PATTERN.finditer(value)})
    return []


def _format_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _summarize_error(error: BaseException | None) -> dict[str, str] | None:
    if error is None:
        return None
    return {
        "type": type(error).__name__,
        "message": str(error)[:_MAX_PREVIEW_CHARS],
    }
