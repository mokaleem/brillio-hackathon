from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportingAgentSpec:
    name: str = "reporting-agent"
    description: str = "Generate concise internal reports and artifact-backed exports."
    tool_groups: tuple[str, ...] = ("reporting", "python")


def create_agent() -> ReportingAgentSpec:
    """Return a lightweight demo agent spec for registry materialization checks."""
    return ReportingAgentSpec()
