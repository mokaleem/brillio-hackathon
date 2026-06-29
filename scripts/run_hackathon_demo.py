#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import secrets
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from bootstrap_demo import BootstrapResult, bootstrap_demo  # noqa: E402
from hackathon_demo_deploy_smoke import run_demo_deploy_smoke  # noqa: E402

DEMO_ENV_EXAMPLE = Path("docker/hackathon-demo.env.example")
DEMO_ENV = Path("docker/hackathon-demo.env")
COMPOSE_FILE = Path("docker/docker-compose.hackathon-demo.yaml")


@dataclass(frozen=True)
class HackathonDemoLaunchResult:
    project_root: Path
    env_file: Path
    bootstrap_results: tuple[BootstrapResult, ...]
    smoke_detail: str
    started: bool
    command: tuple[str, ...]
    ui_url: str
    gateway_docs_url: str


def run_hackathon_demo(
    project_root: Path = REPO_ROOT,
    *,
    force_bootstrap: bool = False,
    check_compose: bool = True,
    start: bool = True,
    build: bool = True,
) -> HackathonDemoLaunchResult:
    root = project_root.resolve(strict=False)
    bootstrap_results = tuple(bootstrap_demo(root, force=force_bootstrap))
    env_file = seed_demo_env(root)
    smoke = run_demo_deploy_smoke(root, check_compose_config=check_compose)
    ports = read_demo_ports(env_file)
    command = compose_command(root, env_file=env_file, build=build, detach=True)

    if start:
        if shutil.which("docker") is None:
            raise RuntimeError("Docker CLI is required to start the hackathon demo stack.")
        completed = subprocess.run(command, cwd=root, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"docker compose up failed with exit code {completed.returncode}")

    return HackathonDemoLaunchResult(
        project_root=root,
        env_file=env_file,
        bootstrap_results=bootstrap_results,
        smoke_detail=smoke.compose_config_detail,
        started=start,
        command=tuple(command),
        ui_url=f"http://localhost:{ports.frontend}",
        gateway_docs_url=f"http://localhost:{ports.gateway}/api/docs",
    )


@dataclass(frozen=True)
class DemoPorts:
    frontend: str = "3000"
    gateway: str = "8001"


def seed_demo_env(project_root: Path) -> Path:
    env_path = project_root / DEMO_ENV
    if env_path.exists():
        return env_path

    example_path = project_root / DEMO_ENV_EXAMPLE
    if not example_path.is_file():
        raise RuntimeError(f"Missing demo env example: {example_path}")

    text = example_path.read_text(encoding="utf-8")
    text = text.replace(
        "BETTER_AUTH_SECRET=replace-with-a-long-random-demo-secret",
        f"BETTER_AUTH_SECRET={secrets.token_urlsafe(48)}",
    )
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(text, encoding="utf-8")
    return env_path


def read_demo_ports(env_path: Path) -> DemoPorts:
    values = _read_env_values(env_path)
    return DemoPorts(
        frontend=values.get("HACKATHON_FRONTEND_PORT", "3000") or "3000",
        gateway=values.get("HACKATHON_GATEWAY_PORT", "8001") or "8001",
    )


def compose_command(
    project_root: Path,
    *,
    env_file: Path,
    build: bool,
    detach: bool,
) -> list[str]:
    command = [
        "docker",
        "compose",
        "-p",
        "deer-flow-demo",
        "--env-file",
        str(env_file),
        "-f",
        str(project_root / COMPOSE_FILE),
        "up",
    ]
    if build:
        command.append("--build")
    if detach:
        command.append("-d")
    return command


def _read_env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap, validate, and start the hackathon split demo.")
    parser.add_argument("--project-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--force-bootstrap", action="store_true")
    parser.add_argument("--skip-compose-check", action="store_true")
    parser.add_argument("--no-start", action="store_true", help="Prepare and validate without running docker compose up.")
    parser.add_argument("--no-build", action="store_true", help="Start without passing --build to docker compose.")
    args = parser.parse_args(argv)

    result = run_hackathon_demo(
        args.project_root,
        force_bootstrap=args.force_bootstrap,
        check_compose=not args.skip_compose_check,
        start=not args.no_start,
        build=not args.no_build,
    )

    print("Hackathon demo ready")
    print(f"Project root: {result.project_root}")
    print(f"Env file: {result.env_file}")
    print(f"Smoke: {result.smoke_detail}")
    print(f"Started: {'yes' if result.started else 'no'}")
    print("Compose command:")
    print("  " + " ".join(result.command))
    print("Judge URLs:")
    print(f"  UI: {result.ui_url}")
    print(f"  Gateway docs: {result.gateway_docs_url}")
    openai_key = os.environ.get("OPENAI_API_KEY") or _read_env_values(result.env_file).get("OPENAI_API_KEY")
    if not openai_key:
        print("Note: set OPENAI_API_KEY in docker/hackathon-demo.env before real model calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
