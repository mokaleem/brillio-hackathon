from __future__ import annotations

import json
import os
import re
from typing import Any

from langchain_core.tools import tool

from deerflow.internal_registry.entrypoints import resolve_python_entrypoint

DEFAULT_ALLOWED_ENTRYPOINTS = {
    "internal_tools.python_examples:summarize_metrics",
}
ALLOWLIST_ENV = "DEERFLOW_PYTHON_FUNCTION_ALLOWLIST"
MAX_RESULT_CHARS = 20000


@tool("python_function")
def python_function(
    entrypoint: str, args_json: str = "[]", kwargs_json: str = "{}"
) -> str:
    """Execute an allowlisted importable Python function with JSON arguments."""
    if entrypoint not in _allowed_entrypoints():
        raise ValueError(f"Python function '{entrypoint}' is not allowlisted.")

    args = _parse_args(args_json)
    kwargs = _parse_kwargs(kwargs_json)
    result = resolve_python_entrypoint(entrypoint)(*args, **kwargs)
    encoded = json.dumps(result, ensure_ascii=False, default=str)
    if len(encoded) > MAX_RESULT_CHARS:
        return encoded[:MAX_RESULT_CHARS] + "...[truncated]"
    return encoded


def _allowed_entrypoints() -> set[str]:
    configured = {
        item.strip()
        for item in re.split(r"[,;]", os.getenv(ALLOWLIST_ENV, ""))
        if item.strip()
    }
    return DEFAULT_ALLOWED_ENTRYPOINTS | configured


def _parse_args(payload: str) -> list[Any]:
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError("args_json must be a JSON array.")
    return data


def _parse_kwargs(payload: str) -> dict[str, Any]:
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("kwargs_json must be a JSON object.")
    return data
