from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from deerflow.config.app_config import AppConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_SCRIPT_PATH = REPO_ROOT / "scripts" / "bootstrap_demo.py"


spec = importlib.util.spec_from_file_location("deerflow_bootstrap_demo", BOOTSTRAP_SCRIPT_PATH)
assert spec is not None
assert spec.loader is not None
bootstrap_demo = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bootstrap_demo
spec.loader.exec_module(bootstrap_demo)


def test_bootstrap_demo_writes_minimal_demo_files(tmp_path: Path) -> None:
    (tmp_path / "frontend").mkdir()

    results = bootstrap_demo.bootstrap_demo(tmp_path)

    assert (tmp_path / "config.yaml").exists()
    assert (tmp_path / ".env").exists()
    assert (tmp_path / "frontend" / ".env").exists()
    assert (tmp_path / "extensions_config.json").exists()
    assert (tmp_path / "registries" / "demo_extensions.json").exists()
    assert {result.relative_path for result in results} == {
        "config.yaml",
        ".env",
        "frontend/.env",
        "extensions_config.json",
        "registries/demo_extensions.json",
    }


def test_bootstrap_demo_does_not_overwrite_existing_files(tmp_path: Path) -> None:
    (tmp_path / "frontend").mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("custom: true\n", encoding="utf-8")

    results = bootstrap_demo.bootstrap_demo(tmp_path)

    assert config_path.read_text(encoding="utf-8") == "custom: true\n"
    assert any(result.relative_path == "config.yaml" and result.status == "skipped" for result in results)


def test_bootstrap_demo_config_is_loadable_without_api_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "frontend").mkdir()
    bootstrap_demo.bootstrap_demo(tmp_path)

    monkeypatch.setenv("DEER_FLOW_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("DEER_FLOW_CONFIG_PATH", str(tmp_path / "config.yaml"))
    monkeypatch.setenv("DEER_FLOW_EXTENSIONS_CONFIG_PATH", str(tmp_path / "extensions_config.json"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = AppConfig.from_file(str(tmp_path / "config.yaml"))

    assert config.models[0].name == "demo-gpt-4o-mini"
    assert config.sandbox.use == "deerflow.sandbox.local:LocalSandboxProvider"
    assert config.database.backend == "sqlite"


def test_bootstrap_demo_uses_runtime_extension_manifest_env(tmp_path: Path) -> None:
    (tmp_path / "frontend").mkdir()
    bootstrap_demo.bootstrap_demo(tmp_path)

    env_file = (tmp_path / ".env").read_text(encoding="utf-8")

    assert "DEERFLOW_EXTENSION_MANIFESTS=registries/demo_extensions.json" in env_file
    assert "DEER_FLOW_EXTENSION_MANIFESTS" not in env_file
