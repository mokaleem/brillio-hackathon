from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.gateway.deps import require_admin_user
from deerflow.extensions import ExtensionKind, load_extension_catalog

_ADMIN_REQUIRED_DETAIL = "Admin privileges required to manage extension registry configuration."

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


class ExtensionValidateResponse(BaseModel):
    valid: bool
    count: int
    errors: list[str] = Field(default_factory=list)


class ExtensionEnabledUpdateRequest(BaseModel):
    enabled: bool


class ExtensionUpdateResponse(BaseModel):
    extension: ExtensionResponse


@router.get("/extensions", response_model=ExtensionsListResponse)
async def list_extensions(kind: ExtensionKind | None = Query(default=None)) -> ExtensionsListResponse:
    repo_root = _repo_root()
    catalog = load_extension_catalog(_manifest_paths(repo_root), repo_root=repo_root)
    return _catalog_response(catalog.all(kind=kind))


@router.post("/extensions/validate", response_model=ExtensionValidateResponse)
async def validate_extensions(request: Request) -> ExtensionValidateResponse:
    await require_admin_user(request, detail=_ADMIN_REQUIRED_DETAIL)
    repo_root = _repo_root()
    try:
        catalog = load_extension_catalog(_manifest_paths(repo_root), repo_root=repo_root)
    except Exception as exc:
        return ExtensionValidateResponse(valid=False, count=0, errors=[str(exc)])
    return ExtensionValidateResponse(valid=True, count=len(catalog.extensions), errors=[])


@router.post("/extensions/reload", response_model=ExtensionsListResponse)
async def reload_extensions(request: Request, kind: ExtensionKind | None = Query(default=None)) -> ExtensionsListResponse:
    await require_admin_user(request, detail=_ADMIN_REQUIRED_DETAIL)
    repo_root = _repo_root()
    catalog = load_extension_catalog(_manifest_paths(repo_root), repo_root=repo_root)
    return _catalog_response(catalog.all(kind=kind))


@router.put("/extensions/{kind}/{name}", response_model=ExtensionUpdateResponse)
async def update_extension_enabled(
    request: Request,
    kind: ExtensionKind,
    name: str,
    body: ExtensionEnabledUpdateRequest,
) -> ExtensionUpdateResponse:
    await require_admin_user(request, detail=_ADMIN_REQUIRED_DETAIL)
    repo_root = _repo_root()
    extension = _set_extension_enabled(_manifest_paths(repo_root), kind=kind, name=name, enabled=body.enabled)
    return ExtensionUpdateResponse(extension=ExtensionResponse.model_validate(extension))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _manifest_paths(repo_root: Path) -> list[Path]:
    configured = os.environ.get("DEERFLOW_EXTENSION_MANIFESTS")
    if configured:
        return [Path(path) for path in configured.split(os.pathsep) if path]
    return [repo_root / "registries" / "internal_extensions.example.json"]


def _catalog_response(extensions: list[Any]) -> ExtensionsListResponse:
    return ExtensionsListResponse(
        extensions=[ExtensionResponse.model_validate(extension.model_dump()) for extension in extensions],
        count=len(extensions),
    )


def _set_extension_enabled(paths: list[Path], *, kind: ExtensionKind, name: str, enabled: bool) -> dict[str, Any]:
    for path in paths:
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        extensions = payload.get("extensions")
        if not isinstance(extensions, list):
            continue
        for extension in extensions:
            if not isinstance(extension, dict):
                continue
            if extension.get("kind") == kind.value and extension.get("name") == name:
                extension["enabled"] = enabled
                with path.open("w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2)
                    handle.write("\n")
                return extension
    raise HTTPException(status_code=404, detail=f"Extension '{kind.value}/{name}' was not found.")
