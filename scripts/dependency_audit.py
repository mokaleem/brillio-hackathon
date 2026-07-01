#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = REPO_ROOT / "docs" / "security" / "dependency-audit-baseline.json"
HIGH_RISK_SEVERITIES = {"high", "critical"}
TRUTHY_VALUES = {"1", "true", "yes", "on"}
GHSA_PATTERN = re.compile(r"GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}", re.I)


@dataclass(frozen=True)
class DependencyFinding:
    advisory_id: str
    package: str
    severity: str
    title: str
    url: str
    patched_versions: str
    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class BaselineEntry:
    advisory_id: str
    package: str
    severity: str
    owner: str
    expires: date
    reason: str


@dataclass(frozen=True)
class AuditEvaluation:
    approved: tuple[DependencyFinding, ...]
    unapproved: tuple[DependencyFinding, ...]
    expired: tuple[tuple[DependencyFinding, BaselineEntry], ...]
    stale_baseline_ids: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.unapproved and not self.expired


def collect_pnpm_findings(payload: dict[str, Any]) -> tuple[DependencyFinding, ...]:
    if isinstance(payload.get("advisories"), dict):
        return _collect_legacy_pnpm_findings(payload["advisories"])
    if isinstance(payload.get("vulnerabilities"), dict):
        return _collect_modern_pnpm_findings(payload["vulnerabilities"])
    return ()


def load_baseline(path: Path = DEFAULT_BASELINE) -> tuple[BaselineEntry, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("frontend", {}).get("allow", [])
    if not isinstance(entries, list):
        raise ValueError("frontend.allow must be an array")

    baseline: list[BaselineEntry] = []
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("baseline entries must be objects")
        advisory_id = _normalise_advisory_id(str(item.get("id", "")))
        if not advisory_id:
            raise ValueError("baseline entry is missing a GHSA id")
        baseline.append(
            BaselineEntry(
                advisory_id=advisory_id,
                package=str(item.get("package", "")),
                severity=str(item.get("severity", "")).lower(),
                owner=str(item.get("owner", "")),
                expires=date.fromisoformat(str(item.get("expires", ""))),
                reason=str(item.get("reason", "")),
            )
        )
    return tuple(baseline)


def evaluate_findings(
    findings: tuple[DependencyFinding, ...],
    baseline: tuple[BaselineEntry, ...],
    *,
    today: date | None = None,
) -> AuditEvaluation:
    today = today or date.today()
    baseline_by_id = {entry.advisory_id: entry for entry in baseline}
    current_by_id = {finding.advisory_id: finding for finding in findings}

    approved: list[DependencyFinding] = []
    unapproved: list[DependencyFinding] = []
    expired: list[tuple[DependencyFinding, BaselineEntry]] = []
    for finding in findings:
        entry = baseline_by_id.get(finding.advisory_id)
        if entry is None:
            unapproved.append(finding)
            continue
        if entry.expires < today:
            expired.append((finding, entry))
            continue
        approved.append(finding)

    stale_baseline_ids = sorted(
        advisory_id for advisory_id in baseline_by_id if advisory_id not in current_by_id
    )
    return AuditEvaluation(
        approved=tuple(approved),
        unapproved=tuple(unapproved),
        expired=tuple(expired),
        stale_baseline_ids=tuple(stale_baseline_ids),
    )


def run_dependency_audit(
    project_root: Path = REPO_ROOT,
    *,
    baseline_path: Path = DEFAULT_BASELINE,
    include_python_network_audit: bool = False,
) -> None:
    root = project_root.resolve(strict=False)
    print("Dependency audit gate")
    print(f"Project root: {root}")
    baseline = load_baseline(_resolve_path(root, baseline_path))

    _verify_python_lock(root, include_network_audit=include_python_network_audit)
    findings = _run_frontend_pnpm_audit(root)
    evaluation = evaluate_findings(findings, baseline)
    _print_evaluation(evaluation)
    if not evaluation.ok:
        raise SystemExit(1)
    print("Dependency audit passed.")


def _collect_legacy_pnpm_findings(
    advisories: dict[str, Any]
) -> tuple[DependencyFinding, ...]:
    findings: list[DependencyFinding] = []
    for advisory in advisories.values():
        if not isinstance(advisory, dict):
            continue
        severity = str(advisory.get("severity", "")).lower()
        if severity not in HIGH_RISK_SEVERITIES:
            continue
        advisory_id = _normalise_advisory_id(
            str(
                advisory.get("github_advisory_id")
                or advisory.get("url")
                or advisory.get("id")
                or ""
            )
        )
        if not advisory_id:
            advisory_id = str(advisory.get("id", "unknown"))
        paths = _collect_paths(advisory.get("findings"))
        findings.append(
            DependencyFinding(
                advisory_id=advisory_id,
                package=str(advisory.get("module_name", "unknown")),
                severity=severity,
                title=str(advisory.get("title", "")),
                url=str(advisory.get("url", "")),
                patched_versions=str(advisory.get("patched_versions", "")),
                paths=paths,
            )
        )
    return tuple(sorted(findings, key=lambda finding: finding.advisory_id))


def _collect_modern_pnpm_findings(
    vulnerabilities: dict[str, Any]
) -> tuple[DependencyFinding, ...]:
    findings: dict[tuple[str, str], DependencyFinding] = {}
    for package_name, vulnerability in vulnerabilities.items():
        if not isinstance(vulnerability, dict):
            continue
        for via in vulnerability.get("via", []):
            if not isinstance(via, dict):
                continue
            severity = str(via.get("severity", vulnerability.get("severity", ""))).lower()
            if severity not in HIGH_RISK_SEVERITIES:
                continue
            advisory_id = _normalise_advisory_id(
                str(via.get("url") or via.get("source") or via.get("id") or "")
            )
            if not advisory_id:
                advisory_id = f"{package_name}:{via.get('title', 'unknown')}"
            package = str(via.get("name") or package_name)
            key = (advisory_id, package)
            findings[key] = DependencyFinding(
                advisory_id=advisory_id,
                package=package,
                severity=severity,
                title=str(via.get("title", "")),
                url=str(via.get("url", "")),
                patched_versions=str(via.get("patched_versions", "")),
                paths=(),
            )
    return tuple(sorted(findings.values(), key=lambda finding: finding.advisory_id))


def _collect_paths(raw_findings: object) -> tuple[str, ...]:
    paths: list[str] = []
    if not isinstance(raw_findings, list):
        return ()
    for finding in raw_findings:
        if not isinstance(finding, dict):
            continue
        for path in finding.get("paths", []):
            if isinstance(path, str):
                paths.append(path)
    return tuple(sorted(paths))


def _normalise_advisory_id(value: str) -> str:
    match = GHSA_PATTERN.search(value)
    return match.group(0).upper() if match else ""


def _verify_python_lock(root: Path, *, include_network_audit: bool) -> None:
    backend = root / "backend"
    if not (backend / "uv.lock").is_file():
        raise SystemExit("backend/uv.lock is missing")
    with tempfile.TemporaryDirectory(prefix="deerflow-deps-") as temp_dir:
        requirements = Path(temp_dir) / "requirements.txt"
        _run_checked(
            (
                "uv",
                "export",
                "--locked",
                "--format",
                "requirements-txt",
                "--no-hashes",
                "--output-file",
                str(requirements),
            ),
            cwd=backend,
            label="backend lock export",
        )
        if include_network_audit:
            _run_checked(
                ("uvx", "pip-audit", "-r", str(requirements), "--strict"),
                cwd=root,
                label="backend pip-audit",
            )
        else:
            print(
                "Python lock export passed; set DEERFLOW_RUN_PIP_AUDIT=1 "
                "to run the networked pip-audit check."
            )


def _run_frontend_pnpm_audit(root: Path) -> tuple[DependencyFinding, ...]:
    frontend = root / "frontend"
    if not (frontend / "pnpm-lock.yaml").is_file():
        raise SystemExit("frontend/pnpm-lock.yaml is missing")
    completed = subprocess.run(
        _resolve_command(("pnpm", "audit", "--prod", "--audit-level", "high", "--json")),
        cwd=frontend,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if not completed.stdout.strip():
        raise SystemExit(completed.stderr.strip() or "pnpm audit did not return JSON")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"pnpm audit returned invalid JSON: {exc}") from exc
    findings = collect_pnpm_findings(payload)
    print(f"Frontend pnpm audit found {len(findings)} high/critical advisory id(s).")
    return findings


def _print_evaluation(evaluation: AuditEvaluation) -> None:
    for finding in evaluation.approved:
        print(
            "[BASELINED] "
            f"{finding.advisory_id} {finding.package} {finding.severity} "
            f"patched={finding.patched_versions or 'unknown'}"
        )
    for finding in evaluation.unapproved:
        print(
            "[UNAPPROVED] "
            f"{finding.advisory_id} {finding.package} {finding.severity}: "
            f"{finding.title}"
        )
    for finding, entry in evaluation.expired:
        print(
            "[EXPIRED] "
            f"{finding.advisory_id} {finding.package} expired on {entry.expires}"
        )
    for advisory_id in evaluation.stale_baseline_ids:
        print(f"[STALE BASELINE] {advisory_id} is not present in the current audit.")


def _run_checked(command: tuple[str, ...], *, cwd: Path, label: str) -> None:
    print(f"Running {label}: {' '.join(command)}")
    completed = subprocess.run(
        _resolve_command(command),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode == 0:
        return
    if completed.stdout:
        print(completed.stdout)
    if completed.stderr:
        print(completed.stderr)
    raise subprocess.CalledProcessError(
        completed.returncode,
        command,
        output=completed.stdout,
        stderr=completed.stderr,
    )


def _resolve_command(command: tuple[str, ...]) -> tuple[str, ...]:
    executable = shutil.which(command[0])
    if executable is None:
        return command
    return (executable, *command[1:])


def _resolve_path(root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return root / path


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in TRUTHY_VALUES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run dependency audit release gate.")
    parser.add_argument("--project-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--include-python-network-audit",
        action="store_true",
        help="Run uvx pip-audit against the exported backend requirements.",
    )
    args = parser.parse_args(argv)

    run_dependency_audit(
        args.project_root,
        baseline_path=args.baseline,
        include_python_network_audit=args.include_python_network_audit
        or _is_truthy(os.environ.get("DEERFLOW_RUN_PIP_AUDIT")),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
