# Internal Extension Registry (fork)

Moved out of `backend/AGENTS.md` to keep the AGENTS.md chain under upstream's size limit (`scripts/check_agent_guidance.py`).

The hackathon extension layer lives in the harness package under `packages/harness/deerflow/internal_registry/` and remains importable without FastAPI. It provides:
- `ExtensionManifest` / `ExtensionDescriptor` models for `agent`, `mcp`, `tool`, and `skill` descriptors.
- `load_extension_manifest()` and `load_extension_catalog()` for side-effect-free manifest loading and duplicate detection.
- `resolve_python_entrypoint()` / `execute_python_entrypoint()` for explicit `module:function` execution.
- Materializers that convert descriptors into native runtime shapes: `BaseTool`, `ToolConfig`, `McpServerConfig`, skill paths, and agent factory callables.

Company-owned extension implementations live outside the harness in `internal_agents/`, `internal_mcps/`, `internal_tools/`, and `internal_skills/`. Example manifests live under `registries/`, with `registries/internal_extensions.example.json` used by default.

The Gateway exposes the catalog at `GET /api/extensions` and supports `?kind=agent|mcp|tool|skill`. Admin-only endpoints validate (`POST /api/extensions/validate`), reload/list (`POST /api/extensions/reload`), and toggle (`PUT /api/extensions/{kind}/{name}`) manifest entries. Override the manifest list with `DEERFLOW_EXTENSION_MANIFESTS` using the OS path separator.

Enabled `tool` descriptors are materialized and appended by `deerflow.tools.tools.get_available_tools()`, after configured tools and before built-ins, MCP tools, and ACP tools. This keeps registry tools available to orchestration while preserving existing duplicate-name precedence.

The run worker synthesizes `event: events` SSE frames when `events` is requested in stream mode. These frames carry LangChain-shaped orchestration events (`on_run_start`, chunk stream events, `on_run_end`) without dropping the normal `values` snapshots used by the UI.

`deerflow.internal_registry` is this fork's JSON-manifest catalog and is deliberately separate from upstream's `deerflow.extensions` plugin system (packaged Python extensions loaded from `config.yaml -> plugins:`); do not merge the two namespaces.

`"events"` is registered as a fork-only public stream mode in `deerflow/runtime/stream_modes.py` and mapped to LangGraph's `updates` mode by `to_langgraph_stream_modes()`; without that entry the Gateway rejects the frontend's chat requests with `UnsupportedStreamModeError`.

Report artifact helpers live under `packages/harness/deerflow/artifacts/` and currently provide `generate_html_report`, `generate_csv_file`, and `generate_pdf_report`.

Package import hygiene: the `deerflow.agents` and `deerflow.subagents` package
roots expose heavyweight graph/executor entrypoints lazily. The
`deerflow.agents:make_lead_agent` LangGraph Server entrypoint is a concrete thin
module-level function because the server resolves graph factories directly from
the module dictionary; the wrapper keeps the lead-agent and skill-cache imports
inside the function so importing the package remains lightweight. Internal
modules that only need lightweight types, config, or registries should import
the concrete submodule instead of adding eager package-root imports that pull in
the tool graph or subagent executor during state/schema imports.

`ThreadMetaStore.search()` keeps JSON filter semantics identical across memory,
SQLite, and PostgreSQL: missing differs from null, bool differs from int, and
float filters accept integer or real JSON numbers through `json_value_matches`.
