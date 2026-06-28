from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from deerflow.artifacts import generate_csv_file, generate_html_report, generate_pdf_report
from deerflow.extensions import (
    ExtensionCatalog,
    ExtensionDescriptor,
    ExtensionKind,
    ExtensionManifest,
    ExtensionRegistryHealth,
    ExtensionSource,
    RegistryImport,
    load_extension_catalog,
    load_extension_manifest,
    validate_extension_registry,
)

try:
    __version__ = version("deerflow-harness")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "DeerFlowClient",
    "ExtensionCatalog",
    "ExtensionDescriptor",
    "ExtensionKind",
    "ExtensionManifest",
    "ExtensionRegistryHealth",
    "ExtensionSource",
    "RegistryImport",
    "StreamEvent",
    "__version__",
    "generate_csv_file",
    "generate_html_report",
    "generate_pdf_report",
    "load_extension_catalog",
    "load_extension_manifest",
    "validate_extension_registry",
]


def __getattr__(name: str) -> Any:
    if name in {"DeerFlowClient", "StreamEvent"}:
        from deerflow.client import DeerFlowClient, StreamEvent

        return {"DeerFlowClient": DeerFlowClient, "StreamEvent": StreamEvent}[name]
    raise AttributeError(f"module 'deerflow' has no attribute {name!r}")
