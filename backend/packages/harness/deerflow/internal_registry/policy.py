from __future__ import annotations

import os
from dataclasses import dataclass

from deerflow.internal_registry.descriptors import ExtensionDescriptor

DEFAULT_ALLOWED_RISK_LEVELS = frozenset({"low", "medium"})
VALID_RISK_LEVELS = frozenset({"low", "medium", "high"})
RUNTIME_RISK_ENV_VAR = "DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS"
REQUIRE_HIGH_RISK_APPROVAL_ENV_VAR = "DEERFLOW_EXTENSION_REQUIRE_HIGH_RISK_APPROVAL"
_FALSE_VALUES = {"0", "false", "no", "off"}


class ExtensionPermissionError(PermissionError):
    """Raised when a runtime extension violates the configured execution policy."""


@dataclass(frozen=True)
class ExtensionRuntimePolicy:
    allowed_risk_levels: frozenset[str] = DEFAULT_ALLOWED_RISK_LEVELS
    require_high_risk_approval: bool = True

    @classmethod
    def from_environment(cls) -> ExtensionRuntimePolicy:
        return cls(
            allowed_risk_levels=_parse_allowed_risk_levels(os.getenv(RUNTIME_RISK_ENV_VAR)),
            require_high_risk_approval=_parse_require_high_risk_approval(os.getenv(REQUIRE_HIGH_RISK_APPROVAL_ENV_VAR)),
        )

    def require_allowed(self, extension: ExtensionDescriptor) -> None:
        risk_level = extension.risk_level or "medium"
        if risk_level not in self.allowed_risk_levels:
            allowed = ", ".join(sorted(self.allowed_risk_levels))
            raise ExtensionPermissionError(
                f"{extension.kind.value}:{extension.name} risk_level={risk_level!r} is blocked by runtime extension policy. Set {RUNTIME_RISK_ENV_VAR} to include {risk_level!r} after approval. Currently allowed: {allowed}."
            )
        if risk_level == "high" and self.require_high_risk_approval:
            approval = extension.approval
            if approval is None or approval.status != "approved":
                raise ExtensionPermissionError(
                    f"{extension.kind.value}:{extension.name} risk_level='high' requires descriptor approval metadata with status='approved'. Set {REQUIRE_HIGH_RISK_APPROVAL_ENV_VAR}=false only for explicitly trusted local development."
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


def _parse_require_high_risk_approval(value: str | None) -> bool:
    if value is None or not value.strip():
        return True
    return value.strip().lower() not in _FALSE_VALUES
