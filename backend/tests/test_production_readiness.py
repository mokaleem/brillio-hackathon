from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "production_readiness.py"

spec = importlib.util.spec_from_file_location("production_readiness", SCRIPT_PATH)
assert spec is not None
assert spec.loader is not None
production_readiness = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = production_readiness
spec.loader.exec_module(production_readiness)


def test_demo_profile_passes_repository_readiness_checks() -> None:
    results = production_readiness.run_readiness_checks(REPO_ROOT)

    assert all(result.ok for result in results)
    assert [result.name for result in results] == [
        "required paths",
        "demo registry",
        "import guardrails",
        "admin readiness endpoint",
        "runtime approval policy",
        "retention controls",
        "generated registry isolation",
        "frontend env example",
        "demo docs",
        "demo deploy bundle",
    ]


def test_enterprise_profile_accepts_hardened_runtime_env(tmp_path: Path) -> None:
    env_file = tmp_path / "enterprise.env"
    env_file.write_text(
        "\n".join(
            [
                "DEER_FLOW_AUTH_DISABLED=0",
                "GATEWAY_ENABLE_DOCS=false",
                "BETTER_AUTH_SECRET=enterprise-secret-value-with-enough-entropy",
                "OPENAI_API_KEY=test-model-credential",
                "DEER_FLOW_TRUSTED_ORIGINS=https://assistant.example.com",
                "GATEWAY_CORS_ORIGINS=https://assistant.example.com",
                "DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS=low,medium",
                "DEERFLOW_PYTHON_FUNCTION_ALLOWLIST=internal_tools.python_examples:summarize_metrics",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = production_readiness._check_enterprise_runtime_env(REPO_ROOT, env_file)

    assert result.ok is True


def test_enterprise_profile_accepts_secret_manager_backed_values(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / "enterprise.env"
    env_file.write_text(
        "\n".join(
            [
                "DEER_FLOW_AUTH_DISABLED=0",
                "GATEWAY_ENABLE_DOCS=false",
                "BETTER_AUTH_SECRET=",
                "OPENAI_API_KEY=",
                "DEER_FLOW_TRUSTED_ORIGINS=https://assistant.example.com",
                "GATEWAY_CORS_ORIGINS=https://assistant.example.com",
                "DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS=low,medium",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BETTER_AUTH_SECRET", "secret-manager-backed-value-with-enough-entropy")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-manager-model-credential")

    result = production_readiness._check_enterprise_runtime_env(REPO_ROOT, env_file)

    assert result.ok is True


def test_enterprise_profile_rejects_demo_runtime_env(tmp_path: Path) -> None:
    env_file = tmp_path / "demo-defaults.env"
    env_file.write_text(
        "\n".join(
            [
                "DEER_FLOW_AUTH_DISABLED=1",
                "GATEWAY_ENABLE_DOCS=true",
                "BETTER_AUTH_SECRET=replace-with-a-long-random-demo-secret",
                "OPENAI_API_KEY=",
                "DEER_FLOW_TRUSTED_ORIGINS=*",
                "GATEWAY_CORS_ORIGINS=*",
                "DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS=low,medium,high",
                "DEERFLOW_PYTHON_FUNCTION_ALLOWLIST=*",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = production_readiness._check_enterprise_runtime_env(REPO_ROOT, env_file)

    assert result.ok is False
    assert "DEER_FLOW_AUTH_DISABLED" in result.detail
    assert "GATEWAY_ENABLE_DOCS" in result.detail
    assert "BETTER_AUTH_SECRET" in result.detail
