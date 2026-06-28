from __future__ import annotations

import os
import sys
from pathlib import Path

from deerflow.config.runtime_paths import project_root
from deerflow.extensions.loader import ExtensionCatalog, load_extension_catalog

EXTENSION_MANIFESTS_ENV = "DEERFLOW_EXTENSION_MANIFESTS"
DEFAULT_EXTENSION_MANIFEST = Path("registries") / "internal_extensions.example.json"


def get_runtime_extension_manifest_paths(*, repo_root: Path | str | None = None) -> list[Path]:
    root = Path(repo_root).resolve(strict=False) if repo_root is not None else project_root()
    configured = os.getenv(EXTENSION_MANIFESTS_ENV)
    if configured:
        return [_resolve_manifest_path(path, root) for path in configured.split(os.pathsep) if path]

    default_manifest = root / DEFAULT_EXTENSION_MANIFEST
    if default_manifest.is_file():
        return [default_manifest]
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
