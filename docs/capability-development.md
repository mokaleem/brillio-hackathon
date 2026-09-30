# Capability Development Guide

Use this guide when adding agents, MCP servers, tools, or registry imports to
the internal assistant. The design rule is simple: harness code stays generic,
company capabilities live outside the harness, and registry JSON decides what is
loaded.

## Directory Layout

| Capability | Internal directory | Registry kind |
| --- | --- | --- |
| Agents | `internal_agents/` | `agent` |
| MCP servers | `internal_mcps/` | `mcp` |
| Tools | `internal_tools/` | `tool` |
| Skills | `internal_skills/` | `skill` |

The harness package is under `backend/packages/harness`. Do not put company
capability implementations there unless they are reusable SDK features.

## Add a Tool Inside the Codebase

1. Create or update a Python module under `internal_tools/`.
2. Use `langchain_core.tools.tool` for callable tools.
3. Keep inputs JSON-friendly and outputs concise.
4. Write generated files through harness artifact helpers when producing
   deliverables.

Example:

```python
from langchain_core.tools import tool

@tool("risk_summary")
def risk_summary(rows_json: str) -> str:
    """Summarize risk rows supplied as a JSON array."""
    ...
```

Register it:

```json
{
  "kind": "tool",
  "name": "risk-summary",
  "enabled": true,
  "source": "local",
  "entrypoint": "internal_tools.risk:risk_summary",
  "description": "Summarize structured risk rows",
  "risk_level": "low",
  "display_name": "Risk Summary",
  "category": "Reporting",
  "metadata": {
    "group": "reporting",
    "input_schema": {
      "rows_json": "JSON array of risk rows"
    }
  }
}
```

## Add an Agent Inside the Codebase

1. Create a module under `internal_agents/`.
2. Expose an importable factory such as `create_agent`.
3. Keep the factory lightweight. It should return metadata/specification or a
   harness-compatible agent object, depending on the target runtime.
4. Register the factory as `module:function`.

Example:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class FinanceAgentSpec:
    name: str = "finance-agent"
    description: str = "Analyze internal finance data."
    tool_groups: tuple[str, ...] = ("finance", "reporting")

def create_agent() -> FinanceAgentSpec:
    return FinanceAgentSpec()
```

Registry descriptor:

```json
{
  "kind": "agent",
  "name": "finance-agent",
  "enabled": true,
  "source": "local",
  "entrypoint": "internal_agents.finance:create_agent",
  "description": "Analyze internal finance data",
  "risk_level": "medium",
  "metadata": {
    "tool_groups": ["finance", "reporting"],
    "skills": ["market-research"],
    "soul": "You are a finance analysis specialist."
  }
}
```

## Add an MCP Server Inside the Codebase

1. Put the MCP implementation under `internal_mcps/`.
2. Prefer stdio MCP for local/internal servers unless the server is already
   hosted.
3. Register command, args, and environment in descriptor metadata.

Registry descriptor:

```json
{
  "kind": "mcp",
  "name": "policy-docs",
  "enabled": true,
  "source": "local",
  "description": "Search internal policy documents",
  "risk_level": "medium",
  "metadata": {
    "type": "stdio",
    "command": "python",
    "args": ["-m", "internal_mcps.policy_docs"],
    "env": {
      "DOCS_ROOT": "$DOCS_ROOT"
    }
  }
}
```

## Import from a Registry

Local manifests live under `registries/`. The default internal example is
`registries/internal_extensions.example.json`; the demo manifest is
`registries/demo_extensions.json`.

Load one or more manifests:

```powershell
$env:DEERFLOW_EXTENSION_MANIFESTS = "registries/demo_extensions.json"
python scripts\production_readiness.py
```

External import flow:

1. Open `/workspace/extensions`.
2. Choose `Import`.
3. Paste/upload/fetch a registry JSON manifest.
4. Preview validation errors and warnings.
5. Import selected descriptors.
6. Confirm the capability appears in the catalog and chat capability menu.

Imported descriptors are written to `registries/imported_extensions.json`, which
is intentionally gitignored.

## Registry Safety Rules

- Admin import rejects invalid JSON, unsupported schema versions, duplicates,
  oversized payloads, and unsafe entrypoints.
- Runtime materialization respects `DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS`.
- High-risk descriptors require `approval.status: "approved"` by default.
- Python function execution is allowlist-only through
  `DEERFLOW_PYTHON_FUNCTION_ALLOWLIST`.
- Rejected imports are captured as audit events without storing raw registry
  JSON.

## Verification

```powershell
python scripts\production_readiness.py
cd backend
uv run pytest tests/test_extensions_router.py tests/test_internal_registry.py -q
cd ..
python scripts\release_smoke.py --skip-e2e
```
