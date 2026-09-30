from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from deerflow.internal_registry.descriptors import ExtensionDescriptor, ExtensionKind, ExtensionManifest
from deerflow.internal_registry.manifest import load_extension_manifest


@dataclass(frozen=True)
class ExtensionCatalog:
    manifests: tuple[ExtensionManifest, ...]
    extensions: tuple[ExtensionDescriptor, ...]
    repo_root: Path

    def all(self, *, kind: ExtensionKind | str | None = None) -> list[ExtensionDescriptor]:
        resolved_kind = ExtensionKind(kind) if isinstance(kind, str) else kind
        if resolved_kind is None:
            return list(self.extensions)
        return [extension for extension in self.extensions if extension.kind is resolved_kind]

    def enabled(self, *, kind: ExtensionKind | str | None = None) -> list[ExtensionDescriptor]:
        return [extension for extension in self.all(kind=kind) if extension.enabled]


def load_extension_catalog(paths: list[Path | str], *, repo_root: Path | str) -> ExtensionCatalog:
    resolved_repo_root = Path(repo_root).resolve(strict=False)
    manifests = tuple(load_extension_manifest(path) for path in paths)
    extensions: list[ExtensionDescriptor] = []
    seen: set[tuple[ExtensionKind, str]] = set()

    for manifest in manifests:
        for extension in manifest.extensions:
            key = (extension.kind, extension.name)
            if key in seen:
                raise ValueError(f"Duplicate extension '{extension.name}' for kind '{extension.kind}'.")
            seen.add(key)
            extensions.append(extension)

    return ExtensionCatalog(manifests=manifests, extensions=tuple(extensions), repo_root=resolved_repo_root)
