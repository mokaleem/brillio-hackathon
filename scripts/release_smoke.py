#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ReleaseSmokeCommand:
    label: str
    cwd: Path
    command: tuple[str, ...]


def build_release_smoke_commands(
    project_root: Path = REPO_ROOT,
    *,
    include_e2e: bool = True,
) -> tuple[ReleaseSmokeCommand, ...]:
    root = project_root.resolve(strict=False)
    backend = root / "backend"
    frontend = root / "frontend"
    commands = [
        ReleaseSmokeCommand(
            "production readiness checks",
            root,
            ("python", "scripts/production_readiness.py"),
        ),
        ReleaseSmokeCommand(
            "dependency audit gate",
            root,
            ("python", "scripts/dependency_audit.py"),
        ),
        ReleaseSmokeCommand(
            "backend router and demo smoke tests",
            backend,
            (
                "uv",
                "run",
                "pytest",
                "tests/test_audit_router.py",
                "tests/test_extensions_router.py",
                "tests/test_readiness_router.py",
                "tests/test_demo_smoke.py",
                "-q",
            ),
        ),
        ReleaseSmokeCommand(
            "backend focused ruff checks",
            backend,
            (
                "uv",
                "run",
                "ruff",
                "check",
                "app/gateway/extension_registry.py",
                "app/gateway/routers/audit.py",
                "app/gateway/routers/extensions.py",
                "app/gateway/routers/readiness.py",
                "app/gateway/app.py",
                "app/gateway/routers/__init__.py",
                "tests/test_audit_router.py",
                "tests/test_extensions_router.py",
                "tests/test_readiness_router.py",
                "tests/test_demo_smoke.py",
            ),
        ),
        ReleaseSmokeCommand(
            "backend format check",
            backend,
            ("uv", "run", "ruff", "format", "--check", "."),
        ),
        ReleaseSmokeCommand(
            "frontend API unit tests",
            frontend,
            (
                "pnpm",
                "test",
                "tests/unit/app/api/health/route.test.ts",
                "tests/unit/core/audit/api.test.ts",
                "tests/unit/core/internal-registry/api.test.ts",
            ),
        ),
        ReleaseSmokeCommand(
            "frontend typecheck",
            frontend,
            ("pnpm", "typecheck"),
        ),
        ReleaseSmokeCommand(
            "frontend lint",
            frontend,
            ("pnpm", "lint"),
        ),
    ]
    if include_e2e:
        commands.append(
            ReleaseSmokeCommand(
                "hackathon chromium e2e",
                frontend,
                (
                    "pnpm",
                    "test:e2e",
                    "tests/e2e/hackathon-demo.spec.ts",
                    "tests/e2e/hackathon-evidence.spec.ts",
                    "--project=chromium",
                    "--reporter=list",
                ),
            )
        )
    return tuple(commands)


def run_release_smoke(
    project_root: Path = REPO_ROOT,
    *,
    include_e2e: bool = True,
    dry_run: bool = False,
) -> None:
    commands = build_release_smoke_commands(project_root, include_e2e=include_e2e)
    for index, step in enumerate(commands, start=1):
        print(f"[{index}/{len(commands)}] {step.label}")
        print(f"  cwd: {step.cwd}")
        print(f"  cmd: {' '.join(step.command)}")
        if dry_run:
            continue
        subprocess.run(_resolve_command(step.command), cwd=step.cwd, check=True)


def _resolve_command(command: tuple[str, ...]) -> tuple[str, ...]:
    executable = shutil.which(command[0])
    if executable is None:
        return command
    return (executable, *command[1:])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the hackathon release smoke gate."
    )
    parser.add_argument("--project-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--skip-e2e",
        action="store_true",
        help="Run backend/frontend fast checks without the Chromium E2E evidence gate.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the release smoke commands without executing them.",
    )
    args = parser.parse_args(argv)

    run_release_smoke(
        args.project_root,
        include_e2e=not args.skip_e2e,
        dry_run=args.dry_run,
    )
    print(
        "Release smoke passed" if not args.dry_run else "Release smoke dry run complete"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
