from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationError

from app.gateway.deps import require_admin_user
from deerflow.extensions import ExtensionDescriptor, ExtensionKind, ExtensionManifest, load_extension_catalog, validate_extension_registry

_ADMIN_REQUIRED_DETAIL = "Admin privileges required to manage extension registry configuration."
_IMPORTED_EXTENSION_MANIFEST = Path("registries") / "imported_extensions.json"

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
    warnings: list[str] = Field(default_factory=list)


class ExtensionHealthResponse(BaseModel):
    valid: bool
    count: int
    manifests: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExtensionEnabledUpdateRequest(BaseModel):
    enabled: bool


class ExtensionUpdateResponse(BaseModel):
    extension: ExtensionResponse


class ExtensionImportPreviewRequest(BaseModel):
    manifest_json: str


class ExtensionImportPreviewResponse(BaseModel):
    valid: bool
    count: int
    extensions: list[ExtensionResponse] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    duplicates: list[str] = Field(default_factory=list)


class ExtensionImportRequest(BaseModel):
    manifest_json: str
    selected: list[str] = Field(default_factory=list)


@router.get("/extensions", response_model=ExtensionsListResponse)
async def list_extensions(kind: ExtensionKind | None = Query(default=None)) -> ExtensionsListResponse:
    repo_root = _repo_root()
    catalog = load_extension_catalog(_manifest_paths(repo_root), repo_root=repo_root)
    return _catalog_response(catalog.all(kind=kind))


@router.post("/extensions/validate", response_model=ExtensionValidateResponse)
async def validate_extensions(request: Request) -> ExtensionValidateResponse:
    await require_admin_user(request, detail=_ADMIN_REQUIRED_DETAIL)
    repo_root = _repo_root()
    health = validate_extension_registry(_manifest_paths(repo_root), repo_root=repo_root)
    return ExtensionValidateResponse(
        valid=health.valid,
        count=health.count,
        errors=list(health.errors),
        warnings=list(health.warnings),
    )


@router.get("/extensions/health", response_model=ExtensionHealthResponse)
async def extension_health(request: Request) -> ExtensionHealthResponse:
    await require_admin_user(request, detail=_ADMIN_REQUIRED_DETAIL)
    repo_root = _repo_root()
    health = validate_extension_registry(_manifest_paths(repo_root), repo_root=repo_root)
    return ExtensionHealthResponse(
        valid=health.valid,
        count=health.count,
        manifests=list(health.manifests),
        errors=list(health.errors),
        warnings=list(health.warnings),
    )


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


@router.post("/extensions/import/preview", response_model=ExtensionImportPreviewResponse)
async def preview_extension_import(request: Request, body: ExtensionImportPreviewRequest) -> ExtensionImportPreviewResponse:
    await require_admin_user(request, detail=_ADMIN_REQUIRED_DETAIL)
    repo_root = _repo_root()
    manifest, errors = _parse_import_manifest(body.manifest_json)
    if manifest is None:
        return ExtensionImportPreviewResponse(valid=False, count=0, errors=errors)
    duplicates = _duplicate_extension_keys(manifest.extensions, repo_root=repo_root)
    warnings = [f"Duplicate extension already configured: {key}" for key in duplicates]
    return ExtensionImportPreviewResponse(
        valid=len(errors) == 0 and len(duplicates) == 0,
        count=len(manifest.extensions),
        extensions=[ExtensionResponse.model_validate(extension.model_dump()) for extension in manifest.extensions],
        errors=errors,
        warnings=warnings,
        duplicates=duplicates,
    )


@router.post("/extensions/import", response_model=ExtensionsListResponse)
async def import_extensions(request: Request, body: ExtensionImportRequest) -> ExtensionsListResponse:
    await require_admin_user(request, detail=_ADMIN_REQUIRED_DETAIL)
    repo_root = _repo_root()
    manifest, errors = _parse_import_manifest(body.manifest_json)
    if manifest is None:
        raise HTTPException(status_code=400, detail=errors[0] if errors else "Invalid extension manifest.")

    selected = set(body.selected)
    extensions_to_import = [extension.model_copy(update={"enabled": True}) for extension in manifest.extensions if not selected or _extension_key(extension) in selected]
    if not extensions_to_import:
        raise HTTPException(status_code=400, detail="Select at least one extension to import.")

    duplicates = _duplicate_extension_keys(extensions_to_import, repo_root=repo_root)
    if duplicates:
        raise HTTPException(status_code=409, detail=f"Duplicate extensions already configured: {', '.join(duplicates)}")

    _append_imported_extensions(repo_root, manifest=manifest, extensions=extensions_to_import)
    catalog = load_extension_catalog(_manifest_paths(repo_root), repo_root=repo_root)
    return _catalog_response(catalog.all())


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _manifest_paths(repo_root: Path) -> list[Path]:
    configured = os.environ.get("DEERFLOW_EXTENSION_MANIFESTS")
    if configured:
        return _with_imported_manifest(
            [_resolve_manifest_path(path, repo_root) for path in configured.split(os.pathsep) if path],
            repo_root,
        )
    return _with_imported_manifest([repo_root / "registries" / "internal_extensions.example.json"], repo_root)


def _resolve_manifest_path(path: str, repo_root: Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = repo_root / resolved
    return resolved


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


def _parse_import_manifest(manifest_json: str) -> tuple[ExtensionManifest | None, list[str]]:
    try:
        payload = json.loads(manifest_json)
        return ExtensionManifest.model_validate(payload), []
    except json.JSONDecodeError as exc:
        return None, [f"Manifest JSON is invalid: {exc.msg}"]
    except ValidationError as exc:
        return None, [error["msg"] for error in exc.errors()]


def _extension_key(extension: ExtensionDescriptor) -> str:
    return f"{extension.kind.value}:{extension.name}"


def _duplicate_extension_keys(extensions: list[ExtensionDescriptor], *, repo_root: Path) -> list[str]:
    catalog = load_extension_catalog(_manifest_paths(repo_root), repo_root=repo_root)
    existing = {_extension_key(extension) for extension in catalog.all()}
    return sorted(_extension_key(extension) for extension in extensions if _extension_key(extension) in existing)


def _append_imported_extensions(repo_root: Path, *, manifest: ExtensionManifest, extensions: list[ExtensionDescriptor]) -> None:
    path = repo_root / _IMPORTED_EXTENSION_MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        imported_manifest = ExtensionManifest.model_validate(payload)
    else:
        imported_manifest = ExtensionManifest(version=1)

    imported_keys = {_extension_key(extension) for extension in imported_manifest.extensions}
    next_extensions = [*imported_manifest.extensions]
    for extension in extensions:
        key = _extension_key(extension)
        if key not in imported_keys:
            next_extensions.append(extension)
            imported_keys.add(key)

    import_keys = {(item.kind, item.name) for item in imported_manifest.imports}
    next_imports = [*imported_manifest.imports]
    for item in manifest.imports:
        key = (item.kind, item.name)
        if key not in import_keys:
            next_imports.append(item)
            import_keys.add(key)

    output = imported_manifest.model_copy(update={"imports": next_imports, "extensions": next_extensions})
    with path.open("w", encoding="utf-8") as handle:
        json.dump(output.model_dump(mode="json", exclude_none=True), handle, indent=2)
        handle.write("\n")


def _with_imported_manifest(paths: list[Path], repo_root: Path) -> list[Path]:
    imported = repo_root / _IMPORTED_EXTENSION_MANIFEST
    if not imported.is_file():
        return paths
    imported_resolved = imported.resolve(strict=False)
    if imported_resolved in {path.resolve(strict=False) for path in paths}:
        return paths
    return [*paths, imported]
