from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "hackathon_demo_deploy_smoke.py"
COMPOSE_PATH = REPO_ROOT / "docker" / "docker-compose.hackathon-demo.yaml"
ENV_EXAMPLE_PATH = REPO_ROOT / "docker" / "hackathon-demo.env.example"

spec = importlib.util.spec_from_file_location("hackathon_demo_deploy_smoke", SCRIPT_PATH)
assert spec is not None
assert spec.loader is not None
deploy_smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = deploy_smoke
spec.loader.exec_module(deploy_smoke)


def test_hackathon_demo_deploy_smoke_validates_bundle_without_docker() -> None:
    result = deploy_smoke.run_demo_deploy_smoke(REPO_ROOT, check_compose_config=False)

    assert result.compose_services == ("frontend", "gateway")
    assert result.compose_config_checked is False


def test_hackathon_demo_compose_mounts_registry_and_internal_capabilities() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    gateway = compose["services"]["gateway"]
    frontend = compose["services"]["frontend"]

    gateway_environment = "\n".join(gateway["environment"])
    frontend_environment = "\n".join(frontend["environment"])
    gateway_volumes = "\n".join(gateway["volumes"])

    assert "DEERFLOW_EXTENSION_MANIFESTS=${DEERFLOW_EXTENSION_MANIFESTS:-registries/demo_extensions.json}" in gateway_environment
    assert "DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS=${DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS:-low,medium}" in gateway_environment
    assert "DEERFLOW_PYTHON_FUNCTION_ALLOWLIST=" in gateway_environment
    assert "DEER_FLOW_AUTH_DISABLED=${DEER_FLOW_AUTH_DISABLED:-1}" in gateway_environment
    assert "DEER_FLOW_INTERNAL_GATEWAY_BASE_URL=http://gateway:8001" in frontend_environment
    assert "/app/registries:ro" in gateway_volumes
    assert "/app/internal_agents:ro" in gateway_volumes
    assert "/app/internal_mcps:ro" in gateway_volumes
    assert "/app/internal_tools:ro" in gateway_volumes
    assert "/app/internal_skills:ro" in gateway_volumes


def test_hackathon_demo_env_example_documents_demo_controls() -> None:
    text = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")

    assert "HACKATHON_FRONTEND_PORT=3000" in text
    assert "HACKATHON_GATEWAY_PORT=8001" in text
    assert "DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS=low,medium" in text
    assert "OPENAI_API_KEY=" in text
