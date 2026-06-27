from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from deerflow.extensions import ExtensionKind, load_extension_catalog

router = APIRouter(prefix="/api", tags=["extensions"])


class ExtensionResponse(BaseModel):
    kind: ExtensionKind
    name: str
    enabled: bool
    source: str
    entrypoint: str | None = None
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[str] | None = None
    requires: list[str] = Field(default_factory=list)
    owner: str | None = None
    risk_level: str | None = None
    display_name: str | None = None
    icon: str | None = None
    category: str | None = None


class ExtensionsListResponse(BaseModel):
    extensions: list[ExtensionResponse]
    count: int


@router.get("/extensions", response_model=ExtensionsListResponse)
async def list_extensions(kind: ExtensionKind | None = Query(default=None)) -> ExtensionsListResponse:
    repo_root = _repo_root()
    catalog = load_extension_catalog(_manifest_paths(repo_root), repo_root=repo_root)
    extensions = catalog.all(kind=kind)
    return ExtensionsListResponse(
        extensions=[ExtensionResponse.model_validate(extension.model_dump()) for extension in extensions],
        count=len(extensions),
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _manifest_paths(repo_root: Path) -> list[Path]:
    configured = os.environ.get("DEERFLOW_EXTENSION_MANIFESTS")
    if configured:
        return [Path(path) for path in configured.split(os.pathsep) if path]
    return [repo_root / "registries" / "internal_extensions.example.json"]
