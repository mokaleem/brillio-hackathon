from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_SMOKE_SCRIPT_PATH = REPO_ROOT / "scripts" / "release_smoke.py"


spec = importlib.util.spec_from_file_location("deerflow_release_smoke", RELEASE_SMOKE_SCRIPT_PATH)
assert spec is not None
assert spec.loader is not None
release_smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = release_smoke
spec.loader.exec_module(release_smoke)


def test_release_smoke_includes_backend_frontend_and_e2e_steps() -> None:
    commands = release_smoke.build_release_smoke_commands(REPO_ROOT)

    labels = [command.label for command in commands]
    assert labels == [
        "production readiness checks",
        "dependency audit gate",
        "backend router and demo smoke tests",
        "backend focused ruff checks",
        "backend format check",
        "frontend API unit tests",
        "frontend typecheck",
        "frontend lint",
        "hackathon chromium e2e",
    ]
    assert commands[0].cwd == REPO_ROOT
    assert commands[0].command == ("python", "scripts/production_readiness.py")
    assert commands[1].command == ("python", "scripts/dependency_audit.py")
    assert "app/gateway/extension_registry.py" in commands[3].command
    assert "tests/unit/app/api/health/route.test.ts" in commands[5].command
    assert commands[-1].cwd == REPO_ROOT / "frontend"
    assert commands[-1].command == (
        "pnpm",
        "test:e2e",
        "tests/e2e/hackathon-demo.spec.ts",
        "tests/e2e/hackathon-evidence.spec.ts",
        "--project=chromium",
        "--reporter=list",
    )


def test_release_smoke_can_skip_e2e_for_fast_local_checks() -> None:
    commands = release_smoke.build_release_smoke_commands(REPO_ROOT, include_e2e=False)

    assert [command.label for command in commands] == [
        "production readiness checks",
        "dependency audit gate",
        "backend router and demo smoke tests",
        "backend focused ruff checks",
        "backend format check",
        "frontend API unit tests",
        "frontend typecheck",
        "frontend lint",
    ]


def test_release_smoke_resolves_platform_command_shims(monkeypatch) -> None:
    monkeypatch.setattr(release_smoke.shutil, "which", lambda name: f"C:/tools/{name}.cmd")

    assert release_smoke._resolve_command(("pnpm", "lint")) == (
        "C:/tools/pnpm.cmd",
        "lint",
    )
