# Extension Registry Schema

This document describes the JSON manifest used to dynamically load agents, MCP servers, tools, and skills. The harness owns loading/materialization. Internal company capabilities live outside the harness in directories such as `internal_agents/`, `internal_mcps/`, `internal_tools/`, and `internal_skills/`. The UI talks to the gateway registry API and does not import harness internals.

Canonical local example: `registries/internal_extensions.example.json`

## Manifest Shape

```json
{
  "version": 1,
  "imports": [],
  "extensions": [],
  "metadata": {}
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `version` | integer | No | Defaults to `1`; must be `>= 1`. |
| `imports` | array of registry imports | No | Declares local directories/files or external registries that operators expect this manifest to reference. |
| `extensions` | array of extension descriptors | No | Capability descriptors loaded into the catalog. |
| `metadata` | object | No | Manifest-level metadata for owners, environment, release notes, or registry provenance. |

Unknown fields are rejected. Extension names must be lowercase hyphen-case with digits allowed, up to 64 characters.

## Registry Import

```json
{
  "name": "internal-tools",
  "kind": "tool",
  "type": "directory",
  "path": "internal_tools",
  "enabled": true,
  "metadata": {}
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | Yes | Hyphen-case import name. |
| `kind` | `agent`, `mcp`, `tool`, `skill` | Yes | Capability family represented by this import. |
| `type` | `directory`, `file`, `registry` | No | Defaults to `directory`. |
| `path` | string | For local imports | Must resolve inside the repository root. |
| `url` | string | For remote registries | Used as registry provenance/configuration; import preview still validates pasted/fetched JSON. |
| `enabled` | boolean | No | Defaults to `true`. |
| `metadata` | object | No | Free-form operational metadata. |

## Extension Descriptor

```json
{
  "kind": "tool",
  "name": "html-report",
  "enabled": true,
  "source": "local",
  "entrypoint": "internal_tools.reporting:html_report",
  "description": "Generate a self-contained HTML report",
  "tags": ["reporting", "artifact"],
  "metadata": {},
  "allowed_tools": null,
  "requires": [],
  "owner": "platform",
  "risk_level": "low",
  "display_name": "HTML Report",
  "icon": null,
  "category": "Reporting"
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `kind` | `agent`, `mcp`, `tool`, `skill` | Yes | Determines how the harness materializes the descriptor. |
| `name` | string | Yes | Stable hyphen-case id. Used in duplicate detection and capability prompts. |
| `enabled` | boolean | No | Defaults to `false`. Imported selected descriptors are enabled by the gateway. |
| `source` | `local`, `registry`, `package`, `url` | No | Defaults to `local`; non-local sources produce import warnings. |
| `entrypoint` | string or null | Depends on kind | Python `module:function` for agents/tools; repo-relative path for skills; usually omitted for MCP descriptors. |
| `description` | string | No | Displayed in registry and capability menus. |
| `tags` | string array | No | Search/filter metadata. |
| `metadata` | object | No | Kind-specific payload and UI prompt metadata. |
| `allowed_tools` | string array or null | No | Skill/agent guardrail metadata. |
| `requires` | string array | No | Human-readable dependency list. |
| `owner` | string or null | No | Owning team/person. |
| `risk_level` | `low`, `medium`, `high`, or null | No | Missing/high risk values produce import warnings. |
| `display_name` | string or null | No | Friendly UI label. |
| `icon` | string or null | No | Reserved for future UI icon hints. |
| `category` | string or null | No | UI grouping or tool config group fallback. |

## Kind-Specific Notes

Agents:

```json
{
  "kind": "agent",
  "name": "reporting-agent",
  "enabled": true,
  "source": "local",
  "entrypoint": "internal_agents.reporting:create_agent",
  "description": "Coordinates reporting workflows",
  "metadata": {
    "tool_groups": ["reporting"],
    "skills": [],
    "soul": "You are an internal reporting specialist."
  }
}
```

Tools:

```json
{
  "kind": "tool",
  "name": "csv-export",
  "enabled": true,
  "source": "local",
  "entrypoint": "internal_tools.reporting:csv_export",
  "metadata": {
    "group": "reporting",
    "input_schema": {
      "rows_json": "JSON array of row objects"
    }
  }
}
```

MCP servers:

```json
{
  "kind": "mcp",
  "name": "local-docs",
  "enabled": false,
  "source": "local",
  "description": "Internal documentation search",
  "metadata": {
    "type": "stdio",
    "command": "python",
    "args": ["-m", "internal_mcps.local_docs"],
    "env": {
      "DOCS_ROOT": "$DOCS_ROOT"
    }
  }
}
```

Skills:

```json
{
  "kind": "skill",
  "name": "market-research",
  "enabled": false,
  "source": "local",
  "entrypoint": "internal_skills/market-research",
  "allowed_tools": ["web_search", "html-report", "csv-export"],
  "risk_level": "medium"
}
```

## UI Prompt Metadata

The chat capability menu reads optional metadata to create useful prompts:

| Metadata key | Type | Behavior |
| --- | --- | --- |
| `prompt_template` | string | Used as the inserted prompt. Supports `{{display_name}}`, `{{name}}`, `{{kind}}`, `{{entrypoint}}`, `{{description}}`, and `{{category}}`. |
| `example_prompts` | string array | First example is used when no `prompt_template` exists. |
| `input_schema` | object | Display/documentation hint for expected tool inputs. |
| `group` | string | Tool configuration group. |

## Loading Configuration

Set one or more manifest paths with the platform separator:

```powershell
$env:DEERFLOW_EXTENSION_MANIFESTS = "registries/internal_extensions.example.json"
```

Relative paths resolve against the repository root. If unset, the gateway uses `registries/internal_extensions.example.json` and appends `registries/imported_extensions.json` when it exists.

Admin import writes selected descriptors to:

```text
registries/imported_extensions.json
```

That generated file is gitignored by default.

## Import Guardrails

Registry import is admin-only and fails closed.

| Setting | Default | Purpose |
| --- | --- | --- |
| `DEERFLOW_EXTENSION_IMPORT_MAX_BYTES` | `524288` | Maximum manifest JSON payload size. |
| `DEERFLOW_EXTENSION_IMPORT_MAX_EXTENSIONS` | `200` | Maximum descriptors per imported manifest. |
| `DEERFLOW_EXTENSION_IMPORT_ENTRYPOINT_PREFIXES` | `internal_tools.,internal_agents.,internal_mcps.,internal_skills/,company_tools.,company_agents.,company_skills/,deerflow.` | Comma-separated allowed entrypoint prefixes. Use `*` only in trusted local development. |

Blocked by default:

- Invalid JSON or schema violations.
- Oversized manifests or too many descriptors.
- Duplicate `kind:name` keys already configured.
- Python tool/agent entrypoints that are not `module:function`.
- Path traversal, absolute paths, backslashes, control characters, or entrypoints outside the allowed prefix list.

Preview warnings:

- Non-local source values: `registry`, `package`, or `url`.
- Missing `risk_level`.
- `risk_level: "high"`.
- Duplicate descriptors.

## Minimal External Registry Example

```json
{
  "version": 1,
  "metadata": {
    "registry": "finance-demo",
    "reviewed_by": "platform"
  },
  "extensions": [
    {
      "kind": "tool",
      "name": "forecast-export",
      "enabled": false,
      "source": "registry",
      "entrypoint": "company_tools.forecast:export",
      "description": "Export forecast rows to a reviewed CSV format",
      "tags": ["finance", "artifact"],
      "risk_level": "medium",
      "display_name": "Forecast Export",
      "metadata": {
        "prompt_template": "Use {{display_name}} to export forecast rows for ",
        "input_schema": {
          "rows_json": "JSON array of forecast rows"
        }
      }
    }
  ]
}
```

Import path:

1. Open `/workspace/extensions`.
2. Click `Import`.
3. Paste, upload, or fetch registry JSON.
4. Click `Preview` and review warnings/errors.
5. Select descriptors and click `Import Selected`.
6. Return to chat and open `Capabilities`.
