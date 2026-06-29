from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = Path("docker/docker-compose.hackathon-demo.yaml")
ENV_EXAMPLE_PATH = Path("docker/hackathon-demo.env.example")
SPLIT_DOC_PATH = Path("docs/split-ui-deployment.md")


@dataclass(frozen=True)
class DemoDeploySmokeResult:
    compose_path: Path
    env_example_path: Path
    docs_path: Path
    compose_services: tuple[str, ...]
    compose_config_checked: bool
    compose_config_detail: str


def run_demo_deploy_smoke(
    project_root: Path = REPO_ROOT,
    *,
    check_compose_config: bool = True,
    require_docker: bool = False,
) -> DemoDeploySmokeResult:
    root = project_root.resolve(strict=False)
    compose_path = root / COMPOSE_PATH
    env_example_path = root / ENV_EXAMPLE_PATH
    docs_path = root / SPLIT_DOC_PATH

    _require_files(compose_path, env_example_path, docs_path)
    compose = _read_compose(compose_path)
    services = tuple(sorted(compose.get("services", {})))
    _validate_compose_shape(compose)
    _validate_env_example(env_example_path)
    _validate_docs(docs_path)

    compose_config_checked = False
    compose_config_detail = "skipped"
    if check_compose_config:
        compose_config_checked, compose_config_detail = _run_compose_config(root, require_docker=require_docker)

    return DemoDeploySmokeResult(
        compose_path=compose_path,
        env_example_path=env_example_path,
        docs_path=docs_path,
        compose_services=services,
        compose_config_checked=compose_config_checked,
        compose_config_detail=compose_config_detail,
    )


def _require_files(*paths: Path) -> None:
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError("Missing demo deployment files: " + ", ".join(str(path) for path in missing))


def _read_compose(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a YAML object")
    return payload


def _validate_compose_shape(compose: dict) -> None:
    services = compose.get("services")
    if not isinstance(services, dict):
        raise RuntimeError("Compose file must define services")
    expected_services = {"frontend", "gateway"}
    actual_services = set(services)
    if actual_services != expected_services:
        raise RuntimeError(f"Compose services must be frontend and gateway only; got {sorted(actual_services)}")

    frontend = services["frontend"]
    gateway = services["gateway"]
    frontend_environment = _environment_values(frontend)
    gateway_environment = _environment_values(gateway)
    gateway_volumes = [str(item) for item in gateway.get("volumes", [])]

    _require_contains(frontend_environment, "DEER_FLOW_INTERNAL_GATEWAY_BASE_URL=http://gateway:8001")
    _require_contains(frontend_environment, "DEER_FLOW_TRUSTED_ORIGINS=")
    _require_contains(gateway_environment, "DEERFLOW_EXTENSION_MANIFESTS=")
    _require_contains(gateway_environment, "DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS=")
    _require_contains(gateway_environment, "DEERFLOW_PYTHON_FUNCTION_ALLOWLIST=")
    _require_contains(gateway_environment, "DEER_FLOW_AUTH_DISABLED=")

    required_mounts = [
        "/app/registries",
        "/app/internal_agents",
        "/app/internal_mcps",
        "/app/internal_tools",
        "/app/internal_skills",
        "/app/skills",
    ]
    missing_mounts = [mount for mount in required_mounts if not any(mount in volume for volume in gateway_volumes)]
    if missing_mounts:
        raise RuntimeError("Gateway demo compose is missing mounts: " + ", ".join(missing_mounts))


def _environment_values(service: dict) -> list[str]:
    environment = service.get("environment", [])
    if isinstance(environment, dict):
        return [f"{key}={value}" for key, value in environment.items()]
    if isinstance(environment, list):
        return [str(item) for item in environment]
    raise RuntimeError("Compose service environment must be a list or object")


def _require_contains(values: list[str], needle: str) -> None:
    if not any(needle in value for value in values):
        raise RuntimeError(f"Missing compose environment setting containing {needle!r}")


def _validate_env_example(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    required = [
        "HACKATHON_FRONTEND_PORT",
        "HACKATHON_GATEWAY_PORT",
        "DEERFLOW_EXTENSION_MANIFESTS",
        "DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS",
        "DEERFLOW_PYTHON_FUNCTION_ALLOWLIST",
        "OPENAI_API_KEY=",
        "BETTER_AUTH_SECRET=",
    ]
    missing = [name for name in required if name not in text]
    if missing:
        raise RuntimeError(f"{path} is missing: {', '.join(missing)}")


def _validate_docs(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    required = [
        "Hackathon Split Demo Bundle",
        "docker-compose.hackathon-demo.yaml",
        "hackathon_demo_deploy_smoke.py",
        "docker/hackathon-demo.env",
    ]
    missing = [phrase for phrase in required if phrase not in text]
    if missing:
        raise RuntimeError(f"{path} is missing: {', '.join(missing)}")


def _run_compose_config(root: Path, *, require_docker: bool) -> tuple[bool, str]:
    docker = shutil.which("docker")
    if docker is None:
        if require_docker:
            raise RuntimeError("Docker CLI is required but was not found on PATH")
        return False, "Docker CLI not found; static bundle checks passed"

    command = [
        docker,
        "compose",
        "-p",
        "deer-flow-demo-smoke",
        "-f",
        str(root / COMPOSE_PATH),
        "config",
        "--quiet",
    ]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError("docker compose config failed: " + detail)
    return True, "docker compose config --quiet passed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the hackathon split demo deployment bundle.")
    parser.add_argument("--project-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--skip-compose",
        action="store_true",
        help="Skip docker compose config validation and run only static bundle checks.",
    )
    parser.add_argument(
        "--require-docker",
        action="store_true",
        help="Fail when Docker is not installed instead of treating compose config as optional.",
    )
    args = parser.parse_args(argv)

    result = run_demo_deploy_smoke(
        args.project_root,
        check_compose_config=not args.skip_compose,
        require_docker=args.require_docker,
    )
    print("Hackathon demo deployment smoke passed")
    print(f"Compose: {result.compose_path}")
    print(f"Env example: {result.env_example_path}")
    print(f"Docs: {result.docs_path}")
    print(f"Services: {', '.join(result.compose_services)}")
    print(f"Compose config: {result.compose_config_detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
