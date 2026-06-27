# Spec: Internal Mini ChatGPT on DeerFlow

## Objective
Build a company-internal mini ChatGPT platform on top of ByteDance DeerFlow. The platform must keep DeerFlow's existing harness/app split while adding a configurable extension system for agents, MCP servers, tools, and skills from local directories or external registries.

Primary users are internal teams that need a chat interface able to discover and use approved company agents, tools, skills, MCP servers, and report-generation capabilities without editing core orchestration code.

## Assumptions
- The backend remains the source of truth for orchestration and streaming.
- The frontend remains replaceable: it consumes HTTP/stream contracts and does not import backend or harness code.
- `backend/packages/harness` remains publishable as `deerflow-harness`.
- Internal agents, MCP definitions, tools, and skills live outside the harness directory.
- Registry imports are manifest-driven JSON files, with optional future support for remote HTTP registries.
- The first implementation slice should be additive and testable without requiring live LLM keys.

## Tech Stack
- Backend: Python 3.12, DeerFlow harness, LangGraph, FastAPI gateway, Pydantic, pytest, ruff.
- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS 4, TanStack Query.
- Configuration: repo-root JSON/YAML files loaded by harness/app APIs.
- Reports and generated files: Python stdlib CSV, HTML generation, and optional PDF via installed document conversion stack.

## Target Architecture

### Layer Boundaries
- `backend/packages/harness/deerflow/`: reusable SDK layer. It owns registry abstractions, extension descriptors, dynamic loaders, orchestration event contracts, and artifact generation utilities.
- `backend/app/`: DeerFlow Gateway API. It exposes registry/extension endpoints and maps harness events to frontend stream payloads.
- `frontend/`: replaceable web UI. It uses only Gateway/LangGraph HTTP contracts.
- `internal_agents/`, `internal_mcps/`, `internal_tools/`, `internal_skills/`: local company extension directories outside the harness.
- `registries/`: manifest files that import local or external extension catalogs.

### Extension System
Create a unified extension catalog with four extension kinds:
- `agent`: points to a Python factory/class or ACP-compatible agent definition.
- `mcp`: points to stdio/SSE/HTTP MCP server config.
- `tool`: points to a Python callable, LangChain `BaseTool`, or factory returning tools.
- `skill`: points to a skill directory containing `SKILL.md`.

Every extension descriptor includes:
- `name`, `kind`, `enabled`, `source`, `entrypoint`, `description`, `tags`, `metadata`.
- Optional safety metadata: `allowed_tools`, `requires`, `owner`, `risk_level`.
- Optional UI metadata: `display_name`, `icon`, `category`.

### Registry Files
Add JSON manifests:
- `registries/internal_extensions.example.json`: imports internal local directories.
- `registries/external_registries.example.json`: declares future external registry URLs or package catalogs.

Example shape:

```json
{
  "version": 1,
  "imports": [
    {
      "name": "internal-tools",
      "kind": "tool",
      "type": "directory",
      "path": "internal_tools"
    }
  ],
  "extensions": [
    {
      "kind": "tool",
      "name": "html_report",
      "enabled": true,
      "source": "local",
      "entrypoint": "internal_tools.reporting:html_report_tool",
      "description": "Generate a self-contained HTML report"
    }
  ]
}
```

### Harness Runtime
The harness should expose:
- A pure catalog loader that reads one or more manifest files and returns validated extension descriptors.
- Kind-specific materializers that convert descriptors into DeerFlow-compatible agents, MCP server configs, tools, and skills.
- A streaming event contract that preserves thinking/progress/tool/artifact/final-answer events for any UI.
- Artifact helpers for Python execution, HTML reports, PDF reports, and CSV files.

### UI Runtime
The frontend should display:
- Chat messages and final answers.
- Thinking/progress events as timeline steps.
- Tool calls, agent handoffs, skill activations, MCP/tool promotion events.
- Generated artifacts with download/open actions.
- Extension browser for available agents, MCPs, tools, and skills.

The UI must not depend on file-system layout. It asks the backend for catalog and stream data.

## Commands
- Root install: `make install`
- Root app dev: `make dev`
- Backend tests: `cd backend && make test`
- Backend focused tests: `cd backend && uv run pytest tests/test_extension_registry.py -v`
- Backend lint: `cd backend && make lint`
- Frontend checks: `cd frontend && pnpm check`
- Frontend tests: `cd frontend && pnpm test`

## Project Structure

```text
backend/packages/harness/deerflow/extensions/
  __init__.py
  descriptors.py
  manifest.py
  loader.py
  materialize.py

backend/packages/harness/deerflow/artifacts/
  __init__.py
  generators.py

backend/tests/
  test_extension_registry.py
  test_artifact_generators.py

internal_agents/
internal_mcps/
internal_tools/
internal_skills/
registries/
docs/hackathon/
```

## Code Style
Use typed, pure modules for loading and validation. Avoid imports from `app.*` in harness code.

```python
from pathlib import Path

from deerflow.extensions import ExtensionCatalog, load_extension_catalog

catalog: ExtensionCatalog = load_extension_catalog(
    [Path("registries/internal_extensions.example.json")],
    repo_root=Path.cwd(),
)
enabled_tools = catalog.enabled(kind="tool")
```

## Testing Strategy
- Unit-test manifest parsing, path normalization, duplicate detection, disabled filtering, and entrypoint validation.
- Unit-test artifact generation for HTML, CSV, and PDF fallback behavior without live LLMs.
- Add integration tests only after the pure catalog layer is stable.
- Keep frontend tests mocked against backend contracts.

## Boundaries
- Always: preserve harness/app dependency direction.
- Always: make registry parsing deterministic and side-effect free.
- Always: default unknown or malformed extensions to disabled/failing closed.
- Ask first: adding new third-party dependencies for PDF generation or remote registries.
- Never: load arbitrary remote code directly from a URL at runtime.
- Never: store secrets inside registry manifests.

## Success Criteria
- A developer can install `deerflow-harness` independently and load an extension catalog without the Gateway app.
- Internal extension directories exist outside the harness.
- JSON manifests can register local and future external extension catalogs.
- Chat orchestration can surface thinking/progress/tool/artifact/final-answer events to a replaceable UI.
- The first backend slices pass focused unit tests and the harness boundary test.

