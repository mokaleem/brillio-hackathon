from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EXTENSION_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class ExtensionKind(StrEnum):
    AGENT = "agent"
    MCP = "mcp"
    TOOL = "tool"
    SKILL = "skill"


class ExtensionSource(StrEnum):
    LOCAL = "local"
    REGISTRY = "registry"
    PACKAGE = "package"
    URL = "url"


class RegistryImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: ExtensionKind
    type: Literal["directory", "file", "registry"] = "directory"
    path: str | None = None
    url: str | None = None
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return validate_extension_name(value)

    def resolve_path(self, repo_root: Path) -> Path:
        if not self.path:
            raise ValueError("Registry import does not define a path.")
        root = repo_root.resolve(strict=False)
        target = (root / self.path).resolve(strict=False)
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("Registry import path must resolve within the repository.") from exc
        return target


class ExtensionProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imported_at: str
    descriptor_hash: str
    registry_version: int
    source_name: str | None = None
    source_path: str | None = None
    source_url: str | None = None


class ExtensionDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ExtensionKind
    name: str
    enabled: bool = False
    source: ExtensionSource = ExtensionSource.LOCAL
    entrypoint: str | None = None
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[str] | None = None
    requires: list[str] = Field(default_factory=list)
    owner: str | None = None
    risk_level: Literal["low", "medium", "high"] | None = None
    display_name: str | None = None
    icon: str | None = None
    category: str | None = None
    provenance: ExtensionProvenance | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return validate_extension_name(value)


class ExtensionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    imports: list[RegistryImport] = Field(default_factory=list)
    extensions: list[ExtensionDescriptor] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def validate_extension_name(value: str) -> str:
    normalized = value.strip()
    if not _EXTENSION_NAME_PATTERN.fullmatch(normalized):
        raise ValueError("Extension name must be hyphen-case using lowercase letters, digits, and hyphens only.")
    return normalized
