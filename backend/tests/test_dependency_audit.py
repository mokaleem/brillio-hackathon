from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "dependency_audit.py"

spec = importlib.util.spec_from_file_location("dependency_audit", SCRIPT_PATH)
assert spec is not None
assert spec.loader is not None
dependency_audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = dependency_audit
spec.loader.exec_module(dependency_audit)


def test_collect_pnpm_findings_extracts_high_legacy_advisories() -> None:
    payload = {
        "advisories": {
            "1": {
                "github_advisory_id": "GHSA-r5fr-rjxr-66jc",
                "module_name": "lodash-es",
                "severity": "high",
                "title": "Command Injection in lodash",
                "url": "https://github.com/advisories/GHSA-r5fr-rjxr-66jc",
                "patched_versions": ">=4.18.0",
                "findings": [{"paths": [".>nextra>lodash-es"]}],
            },
            "2": {
                "github_advisory_id": "GHSA-lowr-lowr-lowr",
                "module_name": "example",
                "severity": "moderate",
            },
        }
    }

    findings = dependency_audit.collect_pnpm_findings(payload)

    assert len(findings) == 1
    assert findings[0].advisory_id == "GHSA-R5FR-RJXR-66JC"
    assert findings[0].package == "lodash-es"
    assert findings[0].paths == (".>nextra>lodash-es",)


def test_evaluate_findings_allows_current_baseline() -> None:
    finding = dependency_audit.DependencyFinding(
        advisory_id="GHSA-R5FR-RJXR-66JC",
        package="lodash-es",
        severity="high",
        title="Command Injection in lodash",
        url="https://github.com/advisories/GHSA-r5fr-rjxr-66jc",
        patched_versions=">=4.18.0",
    )
    baseline = (
        dependency_audit.BaselineEntry(
            advisory_id="GHSA-R5FR-RJXR-66JC",
            package="lodash-es",
            severity="high",
            owner="platform",
            expires=date(2026, 8, 15),
            reason="transitive docs dependency",
        ),
    )

    evaluation = dependency_audit.evaluate_findings((finding,), baseline, today=date(2026, 7, 1))

    assert evaluation.ok is True
    assert evaluation.approved == (finding,)
    assert evaluation.unapproved == ()
    assert evaluation.expired == ()


def test_evaluate_findings_fails_unapproved_and_expired_entries() -> None:
    approved_finding = dependency_audit.DependencyFinding(
        advisory_id="GHSA-R5FR-RJXR-66JC",
        package="lodash-es",
        severity="high",
        title="Command Injection in lodash",
        url="https://github.com/advisories/GHSA-r5fr-rjxr-66jc",
        patched_versions=">=4.18.0",
    )
    new_finding = dependency_audit.DependencyFinding(
        advisory_id="GHSA-NEWW-NEWW-NEWW",
        package="new-package",
        severity="critical",
        title="New critical issue",
        url="https://github.com/advisories/GHSA-neww-neww-neww",
        patched_versions=">=1.0.1",
    )
    baseline = (
        dependency_audit.BaselineEntry(
            advisory_id="GHSA-R5FR-RJXR-66JC",
            package="lodash-es",
            severity="high",
            owner="platform",
            expires=date(2026, 6, 30),
            reason="transitive docs dependency",
        ),
    )

    evaluation = dependency_audit.evaluate_findings((approved_finding, new_finding), baseline, today=date(2026, 7, 1))

    assert evaluation.ok is False
    assert evaluation.unapproved == (new_finding,)
    assert evaluation.expired == ((approved_finding, baseline[0]),)
