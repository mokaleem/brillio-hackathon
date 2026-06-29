from __future__ import annotations

import os
from dataclasses import dataclass

from deerflow.extensions.descriptors import ExtensionDescriptor

DEFAULT_ALLOWED_RISK_LEVELS = frozenset({"low", "medium"})
VALID_RISK_LEVELS = frozenset({"low", "medium", "high"})
RUNTIME_RISK_ENV_VAR = "DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS"


class ExtensionPermissionError(PermissionError):
    """Raised when a runtime extension violates the configured execution policy."""


@dataclass(frozen=True)
class ExtensionRuntimePolicy:
    allowed_risk_levels: frozenset[str] = DEFAULT_ALLOWED_RISK_LEVELS

    @classmethod
    def from_environment(cls) -> ExtensionRuntimePolicy:
        return cls(allowed_risk_levels=_parse_allowed_risk_levels(os.getenv(RUNTIME_RISK_ENV_VAR)))

    def require_allowed(self, extension: ExtensionDescriptor) -> None:
        risk_level = extension.risk_level or "medium"
        if risk_level not in self.allowed_risk_levels:
            allowed = ", ".join(sorted(self.allowed_risk_levels))
            raise ExtensionPermissionError(
                f"{extension.kind.value}:{extension.name} risk_level={risk_level!r} is blocked by runtime extension policy. Set {RUNTIME_RISK_ENV_VAR} to include {risk_level!r} after approval. Currently allowed: {allowed}."
            )


def require_extension_runtime_permission(
    extension: ExtensionDescriptor,
    *,
    policy: ExtensionRuntimePolicy | None = None,
) -> None:
    (policy or ExtensionRuntimePolicy.from_environment()).require_allowed(extension)


def _parse_allowed_risk_levels(value: str | None) -> frozenset[str]:
    if value is None or not value.strip():
        return DEFAULT_ALLOWED_RISK_LEVELS

    parsed = {part.strip().lower() for part in value.split(",") if part.strip()}
    if parsed == {"all"}:
        return VALID_RISK_LEVELS

    unknown = parsed - VALID_RISK_LEVELS
    if unknown:
        raise ExtensionPermissionError(f"{RUNTIME_RISK_ENV_VAR} contains unsupported risk level(s): {', '.join(sorted(unknown))}. Valid values are: {', '.join(sorted(VALID_RISK_LEVELS))}, or all.")
    return frozenset(parsed)
