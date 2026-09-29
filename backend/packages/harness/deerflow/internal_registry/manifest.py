from __future__ import annotations

import json
from pathlib import Path

from deerflow.internal_registry.descriptors import ExtensionManifest


def load_extension_manifest(path: Path | str) -> ExtensionManifest:
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)

    with manifest_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return ExtensionManifest.model_validate(payload)
