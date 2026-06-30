from __future__ import annotations

import os
import sys
from pathlib import Path

from deerflow.config.runtime_paths import project_root
from deerflow.extensions.loader import ExtensionCatalog, load_extension_catalog

EXTENSION_MANIFESTS_ENV = "DEERFLOW_EXTENSION_MANIFESTS"
DEFAULT_EXTENSION_MANIFEST = Path("registries") / "internal_extensions.example.json"
IMPORTED_EXTENSION_MANIFEST = Path("registries") / "imported_extensions.json"


def get_runtime_extension_manifest_paths(*, repo_root: Path | str | None = None) -> list[Path]:
    root = Path(repo_root).resolve(strict=False) if repo_root is not None else project_root()
    configured = os.getenv(EXTENSION_MANIFESTS_ENV)
    if configured:
        return _with_imported_manifest(
            [_resolve_manifest_path(path, root) for path in configured.split(os.pathsep) if path],
            root,
        )

    default_manifest = root / DEFAULT_EXTENSION_MANIFEST
    imported_manifest = root / IMPORTED_EXTENSION_MANIFEST
    if default_manifest.is_file():
        return _with_imported_manifest([default_manifest], root)
    if imported_manifest.is_file():
        return [imported_manifest]
    return []


def load_runtime_extension_catalog(*, repo_root: Path | str | None = None) -> ExtensionCatalog:
    root = Path(repo_root).resolve(strict=False) if repo_root is not None else project_root()
    ensure_project_root_importable(root)
    paths = get_runtime_extension_manifest_paths(repo_root=root)
    if not paths:
        return ExtensionCatalog(manifests=(), extensions=(), repo_root=root)
    return load_extension_catalog(paths, repo_root=root)


def ensure_project_root_importable(root: Path | str) -> None:
    root_text = str(Path(root).resolve(strict=False))
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


def _resolve_manifest_path(path: str, root: Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = root / resolved
    return resolved


def _with_imported_manifest(paths: list[Path], root: Path) -> list[Path]:
    imported_manifest = root / IMPORTED_EXTENSION_MANIFEST
    if not imported_manifest.is_file():
        return paths
    resolved_imported = imported_manifest.resolve(strict=False)
    resolved_paths = [path.resolve(strict=False) for path in paths]
    if resolved_imported in resolved_paths:
        return paths
    return [*paths, imported_manifest]
