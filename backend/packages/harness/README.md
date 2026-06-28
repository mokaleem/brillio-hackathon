# DeerFlow Harness

`deerflow-harness` is the installable SDK layer for DeerFlow orchestration. It
contains the agent harness, extension registry loader, MCP/tool/skill
materializers, artifact generators, and embedded Python client without depending
on the Gateway or frontend app packages.

## Install

```bash
uv add deerflow-harness
```

For local development from this monorepo:

```bash
uv sync --package deerflow-harness
```

## Public API

```python
from pathlib import Path

from deerflow import (
    DeerFlowClient,
    generate_pdf_report,
    load_extension_catalog,
    validate_extension_registry,
)

repo_root = Path.cwd()
manifest = repo_root / "registries" / "internal_extensions.example.json"

health = validate_extension_registry([manifest], repo_root=repo_root)
if not health.valid:
    raise RuntimeError(health.errors)

catalog = load_extension_catalog([manifest], repo_root=repo_root)
print([extension.name for extension in catalog.enabled(kind="tool")])

generate_pdf_report(
    title="Demo Report",
    lines=["Harness installed as a Python dependency."],
    output_path="demo-report.pdf",
)

client = DeerFlowClient()
print(client.chat("Summarize the configured extension registry."))
```

The Gateway and UI are optional deployment layers. A separate UI can talk to the
Gateway over HTTP, while internal Python services can import this package
directly.
