from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationError

from app.gateway.deps import require_admin_user
from deerflow.audit import record_audit_event
from deerflow.extensions import (
    ExtensionApproval,
    ExtensionDescriptor,
    ExtensionKind,
    ExtensionManifest,
    ExtensionProvenance,
    ExtensionSource,
    load_extension_catalog,
    validate_extension_registry,
)

_ADMIN_REQUIRED_DETAIL = "Admin privileges required to manage extension registry configuration."
_IMPORTED_EXTENSION_MANIFEST = Path("registries") / "imported_extensions.json"
_DEFAULT_IMPORT_MAX_BYTES = 512 * 1024
_DEFAULT_IMPORT_MAX_EXTENSIONS = 200
_DEFAULT_IMPORT_SCHEMA_VERSIONS = (1,)
_DEFAULT_ALLOWED_ENTRYPOINT_PREFIXES = (
    "internal_tools.",
    "internal_agents.",
    "internal_mcps.",
    "internal_skills/",
    "company_tools.",
    "company_agents.",
    "company_skills/",
    "deerflow.",
)
_PYTHON_ENTRYPOINT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_.]*$")
_PYTHON_ENTRYPOINT_KINDS = {ExtensionKind.AGENT, ExtensionKind.TOOL}

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
    provenance: ExtensionProvenance | None = None
    approval: ExtensionApproval | None = None


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


class ExtensionImportPreviewChange(BaseModel):
    key: str
    action: Literal["add", "conflict"]
    extension: ExtensionResponse
    existing: ExtensionResponse | None = None
    reason: str | None = None


class ExtensionImportPreviewResponse(BaseModel):
    valid: bool
    count: int
    extensions: list[ExtensionResponse] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    duplicates: list[str] = Field(default_factory=list)
    changes: list[ExtensionImportPreviewChange] = Field(default_factory=list)


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
        _record_import_rejection(operation="preview", manifest_json=body.manifest_json, errors=errors)
        return ExtensionImportPreviewResponse(valid=False, count=0, errors=errors)
    errors.extend(_import_manifest_policy_errors(manifest))
    safety_errors, safety_warnings = _import_safety_messages(manifest.extensions)
    errors.extend(safety_errors)
    changes = _preview_import_changes(manifest.extensions, repo_root=repo_root)
    duplicates = [change.key for change in changes if change.action == "conflict"]
    warnings = [
        *safety_warnings,
        *[f"Duplicate extension already configured: {key}" for key in duplicates],
    ]
    if errors or duplicates:
        _record_import_rejection(
            operation="preview",
            manifest_json=body.manifest_json,
            errors=[*errors, *[f"Duplicate extension already configured: {key}" for key in duplicates]],
            warnings=warnings,
            manifest=manifest,
        )
    return ExtensionImportPreviewResponse(
        valid=len(errors) == 0 and len(duplicates) == 0,
        count=len(manifest.extensions),
        extensions=[ExtensionResponse.model_validate(extension.model_dump()) for extension in manifest.extensions],
        errors=errors,
        warnings=warnings,
        duplicates=duplicates,
        changes=changes,
    )


@router.post("/extensions/import", response_model=ExtensionsListResponse)
async def import_extensions(request: Request, body: ExtensionImportRequest) -> ExtensionsListResponse:
    await require_admin_user(request, detail=_ADMIN_REQUIRED_DETAIL)
    repo_root = _repo_root()
    manifest, errors = _parse_import_manifest(body.manifest_json)
    if manifest is None:
        _record_import_rejection(
            operation="commit",
            manifest_json=body.manifest_json,
            errors=errors,
            selected=body.selected,
        )
        raise HTTPException(status_code=400, detail=errors[0] if errors else "Invalid extension manifest.")
    policy_errors = _import_manifest_policy_errors(manifest)
    if policy_errors:
        _record_import_rejection(
            operation="commit",
            manifest_json=body.manifest_json,
            errors=policy_errors,
            manifest=manifest,
            selected=body.selected,
        )
        raise HTTPException(status_code=400, detail=policy_errors[0])

    selected = set(body.selected)
    extensions_to_import = [extension.model_copy(update={"enabled": True}) for extension in manifest.extensions if not selected or _extension_key(extension) in selected]
    if not extensions_to_import:
        _record_import_rejection(
            operation="commit",
            manifest_json=body.manifest_json,
            errors=["Select at least one extension to import."],
            manifest=manifest,
            selected=body.selected,
        )
        raise HTTPException(status_code=400, detail="Select at least one extension to import.")

    safety_errors, _ = _import_safety_messages(extensions_to_import)
    if safety_errors:
        _record_import_rejection(
            operation="commit",
            manifest_json=body.manifest_json,
            errors=safety_errors,
            manifest=manifest,
            selected=body.selected,
        )
        raise HTTPException(status_code=400, detail=safety_errors[0])

    duplicates = _duplicate_extension_keys(extensions_to_import, repo_root=repo_root)
    if duplicates:
        _record_import_rejection(
            operation="commit",
            manifest_json=body.manifest_json,
            errors=[f"Duplicate extensions already configured: {', '.join(duplicates)}"],
            manifest=manifest,
            selected=body.selected,
        )
        raise HTTPException(status_code=409, detail=f"Duplicate extensions already configured: {', '.join(duplicates)}")

    _append_imported_extensions(repo_root, manifest=manifest, extensions=extensions_to_import)
    catalog = load_extension_catalog(_manifest_paths(repo_root), repo_root=repo_root)
    return _catalog_response(catalog.all())


@router.delete("/extensions/imported/{kind}/{name}", response_model=ExtensionsListResponse)
async def remove_imported_extension(request: Request, kind: ExtensionKind, name: str) -> ExtensionsListResponse:
    await require_admin_user(request, detail=_ADMIN_REQUIRED_DETAIL)
    repo_root = _repo_root()
    _remove_imported_extension(repo_root, kind=kind, name=name)
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
    extension_state = _extension_state(paths)
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
                if enabled:
                    _validate_extension_dependencies(extension, extension_state)
                extension["enabled"] = enabled
                with path.open("w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2)
                    handle.write("\n")
                return extension
    raise HTTPException(status_code=404, detail=f"Extension '{kind.value}/{name}' was not found.")


def _extension_state(paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
    by_name: dict[str, list[dict[str, Any]]] = {}
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
            name = extension.get("name")
            kind = extension.get("kind")
            if not isinstance(name, str) or not isinstance(kind, str):
                continue
            by_name.setdefault(name, []).append(extension)
            by_name.setdefault(f"{kind}:{name}", []).append(extension)
    return by_name


def _validate_extension_dependencies(extension: dict[str, Any], extension_state: dict[str, list[dict[str, Any]]]) -> None:
    requirements = extension.get("requires")
    if not isinstance(requirements, list):
        return

    missing: list[str] = []
    disabled: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, str):
            continue
        candidates = extension_state.get(requirement, [])
        if not candidates:
            missing.append(requirement)
        elif not any(candidate.get("enabled") is True for candidate in candidates):
            disabled.append(requirement)

    problems = []
    if missing:
        problems.append(f"missing: {', '.join(missing)}")
    if disabled:
        problems.append(f"disabled: {', '.join(disabled)}")
    if problems:
        name = extension.get("name", "extension")
        raise HTTPException(
            status_code=409,
            detail=f"Cannot enable extension '{name}' until required capabilities are available ({'; '.join(problems)}).",
        )


def _parse_import_manifest(manifest_json: str) -> tuple[ExtensionManifest | None, list[str]]:
    manifest_size = len(manifest_json.encode("utf-8"))
    max_bytes = _import_max_manifest_bytes()
    if manifest_size > max_bytes:
        return None, [f"Manifest JSON is too large ({manifest_size} bytes). Limit is {max_bytes} bytes."]
    try:
        payload = json.loads(manifest_json)
        manifest = ExtensionManifest.model_validate(payload)
    except json.JSONDecodeError as exc:
        return None, [f"Manifest JSON is invalid: {exc.msg}"]
    except ValidationError as exc:
        return None, [error["msg"] for error in exc.errors()]
    max_extensions = _import_max_extensions()
    if len(manifest.extensions) > max_extensions:
        return None, [f"Manifest contains {len(manifest.extensions)} extensions. Limit is {max_extensions} extensions."]
    return manifest, []


def _record_import_rejection(
    *,
    operation: Literal["preview", "commit"],
    manifest_json: str,
    errors: list[str],
    warnings: list[str] | None = None,
    manifest: ExtensionManifest | None = None,
    selected: list[str] | None = None,
) -> None:
    encoded = manifest_json.encode("utf-8")
    source_identifiers = sorted(_manifest_source_identifiers(manifest)) if manifest else []
    extension_keys = sorted(_extension_key(extension) for extension in manifest.extensions) if manifest else []
    primary_error = errors[0] if errors else "Extension import rejected."
    try:
        record_audit_event(
            event="extension.import.rejected",
            status="rejected",
            extension={
                "kind": "registry",
                "name": _import_audit_source_name(manifest),
                "source": "registry",
                "operation": operation,
            },
            input_summary={
                "operation": operation,
                "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
                "manifest_bytes": len(encoded),
                "selected": sorted(selected or []),
                "extension_count": len(manifest.extensions) if manifest else 0,
                "extension_keys": extension_keys[:20],
                "extension_keys_truncated": len(extension_keys) > 20,
                "source_identifiers": source_identifiers[:20],
                "source_identifiers_truncated": len(source_identifiers) > 20,
            },
            output_summary={
                "error_count": len(errors),
                "errors": errors[:20],
                "errors_truncated": len(errors) > 20,
                "warning_count": len(warnings or []),
                "warnings": (warnings or [])[:20],
                "warnings_truncated": len(warnings or []) > 20,
            },
            artifacts=[],
            error={"type": "ExtensionImportRejected", "message": primary_error},
        )
    except Exception:
        return


def _import_audit_source_name(manifest: ExtensionManifest | None) -> str:
    if manifest is None:
        return "unparsed-manifest"
    source = _select_provenance_source(manifest)
    for key in ("name", "url", "path"):
        value = source.get(key)
        if value:
            return value
    return "unknown-registry"


def _import_safety_messages(extensions: list[ExtensionDescriptor]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    allowed_prefixes = _allowed_import_entrypoint_prefixes()

    for extension in extensions:
        key = _extension_key(extension)
        entrypoint = extension.entrypoint or ""
        if extension.source is not ExtensionSource.LOCAL:
            warnings.append(f"{key} comes from source '{extension.source.value}'. Review registry trust before importing.")
        if extension.risk_level is None:
            warnings.append(f"{key} does not declare a risk_level.")
        elif extension.risk_level == "high":
            warnings.append(f"{key} is marked high risk; review before enabling in production.")

        if not entrypoint:
            if extension.kind in _PYTHON_ENTRYPOINT_KINDS:
                errors.append(f"{key} must define an entrypoint.")
            continue

        if _has_dangerous_entrypoint_path(entrypoint):
            errors.append(f"{key} entrypoint '{entrypoint}' must not contain path traversal or control characters.")
            continue

        if extension.kind in _PYTHON_ENTRYPOINT_KINDS and not _PYTHON_ENTRYPOINT_PATTERN.fullmatch(entrypoint):
            errors.append(f"{key} entrypoint '{entrypoint}' must use module:function syntax.")
            continue

        if not _entrypoint_prefix_allowed(entrypoint, allowed_prefixes):
            errors.append(f"{key} entrypoint '{entrypoint}' is not allowed by DEERFLOW_EXTENSION_IMPORT_ENTRYPOINT_PREFIXES.")

    return errors, warnings


def _has_dangerous_entrypoint_path(entrypoint: str) -> bool:
    return "\x00" in entrypoint or "\r" in entrypoint or "\n" in entrypoint or entrypoint.startswith(("/", "\\")) or ".." in entrypoint or "\\" in entrypoint


def _entrypoint_prefix_allowed(entrypoint: str, allowed_prefixes: tuple[str, ...]) -> bool:
    return "*" in allowed_prefixes or any(entrypoint.startswith(prefix) for prefix in allowed_prefixes)


def _allowed_import_entrypoint_prefixes() -> tuple[str, ...]:
    configured = os.environ.get("DEERFLOW_EXTENSION_IMPORT_ENTRYPOINT_PREFIXES")
    if configured is None:
        return _DEFAULT_ALLOWED_ENTRYPOINT_PREFIXES
    prefixes = tuple(prefix.strip() for prefix in configured.split(",") if prefix.strip())
    return prefixes or _DEFAULT_ALLOWED_ENTRYPOINT_PREFIXES


def _import_max_manifest_bytes() -> int:
    return _env_positive_int("DEERFLOW_EXTENSION_IMPORT_MAX_BYTES", _DEFAULT_IMPORT_MAX_BYTES)


def _import_max_extensions() -> int:
    return _env_positive_int("DEERFLOW_EXTENSION_IMPORT_MAX_EXTENSIONS", _DEFAULT_IMPORT_MAX_EXTENSIONS)


def _import_manifest_policy_errors(manifest: ExtensionManifest) -> list[str]:
    errors: list[str] = []
    supported_versions = _supported_import_schema_versions()
    if manifest.version not in supported_versions:
        errors.append(f"Unsupported extension registry schema version {manifest.version}. Supported versions: {', '.join(str(version) for version in supported_versions)}.")

    allowed_sources = _allowed_import_sources()
    if allowed_sources:
        source_identifiers = _manifest_source_identifiers(manifest)
        if not source_identifiers:
            errors.append("Imported registry must declare source metadata when DEERFLOW_EXTENSION_IMPORT_ALLOWED_SOURCES is configured.")
        elif "*" not in allowed_sources and source_identifiers.isdisjoint(allowed_sources):
            errors.append("Imported registry source is not allowed by DEERFLOW_EXTENSION_IMPORT_ALLOWED_SOURCES.")
    return errors


def _supported_import_schema_versions() -> tuple[int, ...]:
    configured = os.environ.get("DEERFLOW_EXTENSION_IMPORT_SCHEMA_VERSIONS")
    if not configured:
        return _DEFAULT_IMPORT_SCHEMA_VERSIONS
    versions: list[int] = []
    for item in configured.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        try:
            version = int(stripped)
        except ValueError:
            continue
        if version >= 1:
            versions.append(version)
    return tuple(sorted(set(versions))) or _DEFAULT_IMPORT_SCHEMA_VERSIONS


def _allowed_import_sources() -> set[str]:
    configured = os.environ.get("DEERFLOW_EXTENSION_IMPORT_ALLOWED_SOURCES")
    if configured is None:
        return set()
    return {item.strip() for item in configured.split(",") if item.strip()}


def _manifest_source_identifiers(manifest: ExtensionManifest) -> set[str]:
    identifiers: set[str] = set()
    for key in ("registry", "name", "url", "source_url", "path", "source_path"):
        value = manifest.metadata.get(key)
        if isinstance(value, str) and value.strip():
            identifiers.update(_source_identifier_variants(value))
    for item in manifest.imports:
        identifiers.update(_source_identifier_variants(item.name))
        if item.url:
            identifiers.update(_source_identifier_variants(item.url))
        if item.path:
            identifiers.update(_source_identifier_variants(item.path))
    return identifiers


def _source_identifier_variants(value: str) -> set[str]:
    stripped = value.strip()
    variants = {stripped}
    parsed = urlparse(stripped)
    if parsed.hostname:
        variants.add(parsed.hostname)
    return variants


def _env_positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _extension_key(extension: ExtensionDescriptor) -> str:
    return f"{extension.kind.value}:{extension.name}"


def _duplicate_extension_keys(extensions: list[ExtensionDescriptor], *, repo_root: Path) -> list[str]:
    changes = _preview_import_changes(extensions, repo_root=repo_root)
    return sorted(change.key for change in changes if change.action == "conflict")


def _preview_import_changes(
    extensions: list[ExtensionDescriptor],
    *,
    repo_root: Path,
) -> list[ExtensionImportPreviewChange]:
    catalog = load_extension_catalog(_manifest_paths(repo_root), repo_root=repo_root)
    existing = {_extension_key(extension): extension for extension in catalog.all()}
    changes: list[ExtensionImportPreviewChange] = []
    for extension in extensions:
        key = _extension_key(extension)
        existing_extension = existing.get(key)
        changes.append(
            ExtensionImportPreviewChange(
                key=key,
                action="conflict" if existing_extension else "add",
                extension=ExtensionResponse.model_validate(extension.model_dump()),
                existing=ExtensionResponse.model_validate(existing_extension.model_dump()) if existing_extension else None,
                reason="Extension already exists in the active catalog." if existing_extension else None,
            )
        )
    return changes


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
            next_extensions.append(_with_import_provenance(extension, manifest=manifest))
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


def _remove_imported_extension(repo_root: Path, *, kind: ExtensionKind, name: str) -> None:
    path = repo_root / _IMPORTED_EXTENSION_MANIFEST
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Imported extension '{kind.value}/{name}' was not found.")

    with path.open("r", encoding="utf-8") as handle:
        imported_manifest = ExtensionManifest.model_validate(json.load(handle))

    key = f"{kind.value}:{name}"
    next_extensions = [extension for extension in imported_manifest.extensions if _extension_key(extension) != key]
    if len(next_extensions) == len(imported_manifest.extensions):
        raise HTTPException(status_code=404, detail=f"Imported extension '{kind.value}/{name}' was not found.")

    output = imported_manifest.model_copy(update={"extensions": next_extensions})
    with path.open("w", encoding="utf-8") as handle:
        json.dump(output.model_dump(mode="json", exclude_none=True), handle, indent=2)
        handle.write("\n")


def _with_import_provenance(extension: ExtensionDescriptor, *, manifest: ExtensionManifest) -> ExtensionDescriptor:
    source_import = _select_provenance_source(manifest)
    provenance = ExtensionProvenance(
        imported_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        descriptor_hash=_descriptor_hash(extension),
        registry_version=manifest.version,
        source_name=source_import.get("name"),
        source_path=source_import.get("path"),
        source_url=source_import.get("url"),
    )
    return extension.model_copy(update={"provenance": provenance})


def _select_provenance_source(manifest: ExtensionManifest) -> dict[str, str | None]:
    registry_name = manifest.metadata.get("registry") or manifest.metadata.get("name")
    source_url = manifest.metadata.get("url") or manifest.metadata.get("source_url")
    source_path = manifest.metadata.get("path") or manifest.metadata.get("source_path")
    if any(isinstance(value, str) and value.strip() for value in (registry_name, source_url, source_path)):
        return {
            "name": registry_name.strip() if isinstance(registry_name, str) else None,
            "url": source_url.strip() if isinstance(source_url, str) else None,
            "path": source_path.strip() if isinstance(source_path, str) else None,
        }

    for item in manifest.imports:
        if item.type == "registry" and item.url:
            return {"name": item.name, "url": item.url, "path": None}
        if item.path:
            return {"name": item.name, "url": None, "path": item.path}
    return {"name": None, "url": None, "path": None}


def _descriptor_hash(extension: ExtensionDescriptor) -> str:
    payload = extension.model_dump(mode="json", exclude_none=True, exclude={"provenance"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _with_imported_manifest(paths: list[Path], repo_root: Path) -> list[Path]:
    imported = repo_root / _IMPORTED_EXTENSION_MANIFEST
    if not imported.is_file():
        return paths
    imported_resolved = imported.resolve(strict=False)
    if imported_resolved in {path.resolve(strict=False) for path in paths}:
        return paths
    return [*paths, imported]
