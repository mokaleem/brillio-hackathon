# Hackathon Demo Guide

This walkthrough is the short judge path for the internal DeerFlow assistant. It shows dynamic agents, MCPs, tools, and skills loaded from registries while keeping the harness, UI, and internal extensions separable.

## Pitch

This app turns DeerFlow into a configurable internal ChatGPT-style platform. The harness can be installed as a Python SDK, the UI can live as a separate codebase, and company-owned agents, MCP servers, tools, and skills live outside the harness under `internal_agents/`, `internal_mcps/`, `internal_tools/`, and `internal_skills/`.

The key proof points are:

- Registry-driven dynamic loading for agents, MCPs, tools, and skills.
- Admin registry management with validation, health, toggles, and import preview.
- Chat capability picker with a one-click hackathon demo prompt.
- Live run trace and capability execution audit rows surfaced in the UI and persisted to thread state for refresh/export.
- Artifact tools for HTML, CSV, PDF, plus allowlisted Python function execution.

Registry schema reference: `docs/extension-registry-schema.md`

Split UI deployment reference: `docs/split-ui-deployment.md`

Release package and draft PR brief: `docs/hackathon-release-package.md`

Judge rehearsal runbook: `docs/hackathon-judge-runbook.md`

## Setup

Run from the repository root:

```powershell
make demo-config
```

Add `OPENAI_API_KEY` to `.env`, then verify:

```powershell
make doctor
```

Start the app:

```powershell
make dev
```

Open the workspace, then use the Extension Registry and chat capability menu:

- Registry page: `/workspace/extensions`
- Chat page: `/workspace`

## No-LLM Smoke Check

If model credentials are unavailable, prove the core registry and artifact path without an LLM:

```powershell
make demo-smoke
# or: cd backend; uv run python ../scripts/demo_smoke.py
```

Expected output includes:

- `Demo smoke passed`
- Loaded tools: `csv_export`, `html_report`, `pdf_report`, `python_function`
- Generated artifacts under `.deer-flow/demo-smoke/artifacts/`
- Python function result: `{"average": 20.0, "count": 3, "total": 60.0}`

## Judge Walkthrough

1. Open `/workspace/extensions`.
2. Point out the health panel: manifest paths, validation state, errors, and warnings.
3. Show enabled registry entries for agents, tools, skills, and MCP descriptors.
4. Click `Import`, paste or upload a registry JSON manifest, click `Preview`, select entries, then `Import Selected`.
5. Go to `/workspace`, open `Capabilities`, and choose `Hackathon demo flow`.
6. Send the inserted prompt. It asks the assistant to discover registry capabilities, generate HTML/CSV/PDF artifacts, and run `internal_tools.python_examples:summarize_metrics`.
7. Open `Trace` in the chat header to show run start/end, model events, tool events, and capability audit rows for started/finished/failed executions.
8. Export the conversation as JSON or Markdown. The persisted `Run Trace` is included with the final answer.

## Expected Demo Artifacts

The demo flow should produce:

- HTML report: `html-report-*.html`
- CSV export: `csv-export-*.csv`
- PDF report: `pdf-report-*.pdf`

In the no-LLM smoke path, these appear under:

```text
.deer-flow/demo-smoke/artifacts/
```

In a real chat run, artifact paths appear in the assistant result and the artifacts panel.

## Registry Import Trust Boundary

Registry import is an admin-only operation. Treat external registry JSON as code-adjacent configuration because descriptors can point at Python functions, local skill paths, and MCP process metadata.

The gateway fails closed for oversized manifests, too many descriptors, duplicate capability names, malformed entrypoints, path traversal, and entrypoints outside `DEERFLOW_EXTENSION_IMPORT_ENTRYPOINT_PREFIXES`. The default prefix set allows this repo's internal/company namespaces and DeerFlow-owned entrypoints; production deployments should narrow it to reviewed package namespaces.

The UI enforces the same 512 KiB manifest size limit for uploaded and fetched registries before preview. Pasted JSON is still validated by the gateway. Preview warnings call out non-local sources, missing risk levels, high-risk descriptors, and duplicates so admins can review before importing.

## Fallbacks

If the registry page cannot load:

```powershell
cd backend
uv run pytest tests/test_extensions_router.py -v
```

If the frontend demo prompt is questioned:

```powershell
cd frontend
pnpm test tests/unit/core/internal-registry/browser.test.ts tests/unit/core/internal-registry/api.test.ts
```

If trace persistence or export is questioned:

```powershell
cd frontend
pnpm test tests/unit/core/threads/timeline.test.ts tests/unit/core/threads/export.test.ts
```

If artifact generation is questioned:

```powershell
cd backend
uv run python ../scripts/demo_smoke.py
```

## Architecture Sound Bite

The harness owns orchestration and extension loading. Internal company capabilities live outside the harness. The gateway exposes a registry API. The UI consumes that API through typed frontend helpers, so it can stay in this repo or move to a separate codebase without importing backend internals.
