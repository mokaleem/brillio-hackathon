from __future__ import annotations

import os
from pathlib import Path

IMPORTED_EXTENSION_MANIFEST = Path("registries") / "imported_extensions.json"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def manifest_paths(root: Path) -> list[Path]:
    configured = os.environ.get("DEERFLOW_EXTENSION_MANIFESTS")
    if configured:
        paths = [resolve_manifest_path(path, root) for path in configured.split(os.pathsep) if path]
        return with_imported_manifest(paths, root)
    return with_imported_manifest(
        [root / "registries" / "internal_extensions.example.json"],
        root,
    )


def resolve_manifest_path(path: str, root: Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = root / resolved
    return resolved


def with_imported_manifest(paths: list[Path], root: Path) -> list[Path]:
    imported = root / IMPORTED_EXTENSION_MANIFEST
    if not imported.is_file():
        return paths
    imported_resolved = imported.resolve(strict=False)
    if imported_resolved in {path.resolve(strict=False) for path in paths}:
        return paths
    return [*paths, imported]
