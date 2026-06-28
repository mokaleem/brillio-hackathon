from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deerflow.extensions.descriptors import ExtensionDescriptor, ExtensionKind, ExtensionManifest
from deerflow.extensions.loader import load_extension_catalog
from deerflow.extensions.manifest import load_extension_manifest


@dataclass(frozen=True)
class ExtensionRegistryHealth:
    valid: bool
    count: int
    manifests: tuple[str, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def validate_extension_registry(paths: list[Path | str], *, repo_root: Path | str) -> ExtensionRegistryHealth:
    root = Path(repo_root).resolve(strict=False)
    resolved_paths = tuple(_resolve_manifest_path(path, root) for path in paths)
    errors: list[str] = []
    warnings: list[str] = []
    manifests: list[ExtensionManifest] = []

    for path in resolved_paths:
        try:
            manifest = load_extension_manifest(path)
        except Exception as exc:
            errors.append(f"{path}: {exc}")
            continue
        manifests.append(manifest)
        _validate_imports(manifest, repo_root=root, manifest_path=path, errors=errors)
        _validate_extension_metadata(manifest, manifest_path=path, errors=errors, warnings=warnings)

    if not errors:
        try:
            load_extension_catalog(list(resolved_paths), repo_root=root)
        except Exception as exc:
            errors.append(str(exc))

    count = sum(len(manifest.extensions) for manifest in manifests)
    return ExtensionRegistryHealth(
        valid=not errors,
        count=count,
        manifests=tuple(str(path) for path in resolved_paths),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _validate_imports(
    manifest: ExtensionManifest,
    *,
    repo_root: Path,
    manifest_path: Path,
    errors: list[str],
) -> None:
    for imported in manifest.imports:
        if not imported.enabled:
            continue
        prefix = f"{manifest_path}: import '{imported.name}'"
        if imported.type in ("directory", "file"):
            try:
                target = imported.resolve_path(repo_root)
            except Exception as exc:
                errors.append(f"{prefix}: {exc}")
                continue
            if imported.type == "directory" and not target.is_dir():
                errors.append(f"{prefix}: directory does not exist at {target}")
            if imported.type == "file" and not target.is_file():
                errors.append(f"{prefix}: file does not exist at {target}")
        elif imported.type == "registry" and not _is_http_url(imported.url):
            errors.append(f"{prefix}: registry imports require an http(s) url")


def _validate_extension_metadata(
    manifest: ExtensionManifest,
    *,
    manifest_path: Path,
    errors: list[str],
    warnings: list[str],
) -> None:
    for extension in manifest.extensions:
        prefix = f"{manifest_path}: {extension.kind.value} '{extension.name}'"
        if extension.kind in (ExtensionKind.AGENT, ExtensionKind.TOOL):
            _validate_python_entrypoint(extension, prefix=prefix, errors=errors)
        elif extension.kind is ExtensionKind.SKILL:
            _validate_skill_entrypoint(extension, prefix=prefix, errors=errors)
        elif extension.kind is ExtensionKind.MCP:
            _validate_mcp_descriptor(extension, prefix=prefix, errors=errors)

        metadata = extension.metadata
        _validate_optional_metadata_string(metadata, "prompt_template", prefix=prefix, warnings=warnings)
        _validate_optional_metadata_string_list(metadata, "example_prompts", prefix=prefix, warnings=warnings)
        if "input_schema" in metadata and not isinstance(metadata["input_schema"], dict):
            warnings.append(f"{prefix}: metadata.input_schema should be an object")


def _validate_python_entrypoint(extension: ExtensionDescriptor, *, prefix: str, errors: list[str]) -> None:
    if not extension.entrypoint:
        errors.append(f"{prefix}: entrypoint is required")
        return
    if ":" not in extension.entrypoint:
        errors.append(f"{prefix}: entrypoint must use module:function format")


def _validate_skill_entrypoint(extension: ExtensionDescriptor, *, prefix: str, errors: list[str]) -> None:
    if not extension.entrypoint:
        errors.append(f"{prefix}: entrypoint path is required")


def _validate_mcp_descriptor(extension: ExtensionDescriptor, *, prefix: str, errors: list[str]) -> None:
    metadata = extension.metadata
    transport = metadata.get("type") or metadata.get("transport") or "stdio"
    if transport not in {"stdio", "sse", "http"}:
        errors.append(f"{prefix}: unsupported MCP transport '{transport}'")
        return
    if transport == "stdio" and not _non_empty_string(metadata.get("command")):
        errors.append(f"{prefix}: stdio MCP descriptors require metadata.command")
    if transport in {"sse", "http"} and not _non_empty_string(metadata.get("url")):
        errors.append(f"{prefix}: {transport} MCP descriptors require metadata.url")


def _validate_optional_metadata_string(
    metadata: dict[str, Any],
    key: str,
    *,
    prefix: str,
    warnings: list[str],
) -> None:
    if key in metadata and not _non_empty_string(metadata[key]):
        warnings.append(f"{prefix}: metadata.{key} should be a non-empty string")


def _validate_optional_metadata_string_list(
    metadata: dict[str, Any],
    key: str,
    *,
    prefix: str,
    warnings: list[str],
) -> None:
    value = metadata.get(key)
    if value is None:
        return
    if not isinstance(value, list) or any(not _non_empty_string(item) for item in value):
        warnings.append(f"{prefix}: metadata.{key} should be a list of non-empty strings")


def _resolve_manifest_path(path: Path | str, repo_root: Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = repo_root / resolved
    return resolved.resolve(strict=False)


def _is_http_url(value: str | None) -> bool:
    return value is not None and (value.startswith("https://") or value.startswith("http://"))


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
