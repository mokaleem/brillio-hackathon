from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _python_function_tool():
    root_text = str(REPO_ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    from internal_tools.python_runner import python_function

    return python_function


def test_python_function_executes_default_allowlisted_function() -> None:
    python_function = _python_function_tool()

    output = python_function.invoke(
        {
            "entrypoint": "internal_tools.python_examples:summarize_metrics",
            "kwargs_json": json.dumps({"rows": [{"value": 10}, {"value": 20}]}),
        }
    )

    assert json.loads(output) == {"count": 2, "total": 30.0, "average": 15.0}


def test_python_function_executes_env_allowlisted_function(monkeypatch) -> None:
    python_function = _python_function_tool()
    monkeypatch.setenv("DEERFLOW_PYTHON_FUNCTION_ALLOWLIST", "math:sqrt")

    output = python_function.invoke({"entrypoint": "math:sqrt", "args_json": "[81]"})

    assert json.loads(output) == 9.0


def test_python_function_allowlist_does_not_split_entrypoint_colon(monkeypatch) -> None:
    python_function = _python_function_tool()
    monkeypatch.setattr(os, "pathsep", ":")
    monkeypatch.setenv("DEERFLOW_PYTHON_FUNCTION_ALLOWLIST", "math:sqrt")

    output = python_function.invoke({"entrypoint": "math:sqrt", "args_json": "[16]"})

    assert json.loads(output) == 4.0


def test_python_function_rejects_unapproved_function(monkeypatch) -> None:
    python_function = _python_function_tool()
    monkeypatch.delenv("DEERFLOW_PYTHON_FUNCTION_ALLOWLIST", raising=False)

    with pytest.raises(ValueError, match="not allowlisted"):
        python_function.invoke({"entrypoint": "os:getcwd"})


def test_python_function_requires_json_array_args() -> None:
    python_function = _python_function_tool()

    with pytest.raises(ValueError, match="args_json must be a JSON array"):
        python_function.invoke(
            {
                "entrypoint": "internal_tools.python_examples:summarize_metrics",
                "args_json": "{}",
            }
        )
