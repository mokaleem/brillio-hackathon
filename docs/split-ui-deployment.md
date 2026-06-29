# Split UI Deployment Guide

This guide shows how to deploy DeerFlow with the UI, Gateway, and harness as
separate units. Use it when the frontend lives in another repository, when the
harness is installed as a Python SDK, or when the Gateway is operated as the
only network boundary for internal assistants.

## Target Topology

```text
Browser
  |
  | HTTPS
  v
Frontend service or static host
  |
  | server-side rewrites or direct browser API calls
  v
Gateway API service
  |
  | in-process Python imports
  v
deerflow-harness SDK
  |
  | registry descriptors
  v
internal_agents/ internal_mcps/ internal_tools/ internal_skills/
```

The layers are intentionally independent:

- `backend/packages/harness` is the installable SDK and must not import app UI
  code.
- `backend/app/gateway` is the FastAPI boundary for browser and service calls.
- `frontend` is a Next.js UI that can remain in this repository or move to a
  separate codebase.
- `internal_agents`, `internal_mcps`, `internal_tools`, and `internal_skills`
  hold company capabilities outside the SDK package.
- `registries/*.json` controls which capabilities are loaded.

## Deployment Modes

### Same-origin frontend proxy

Use this mode when the browser talks only to the frontend origin and the
frontend server forwards `/api/*` to the Gateway.

Frontend environment:

```bash
DEER_FLOW_INTERNAL_GATEWAY_BASE_URL="http://gateway.internal:8001"
DEER_FLOW_TRUSTED_ORIGINS="https://assistant.example.com"
```

Do not set `NEXT_PUBLIC_BACKEND_BASE_URL` or
`NEXT_PUBLIC_LANGGRAPH_BASE_URL`. The Next.js rewrites in `frontend/next.config.js`
will proxy:

- `/api/langgraph/*` to the Gateway LangGraph-compatible API.
- `/api/*` to the Gateway REST API.

This is the preferred production shape because the Gateway does not need to be
directly reachable from browsers.

### Split-origin browser access

Use this mode when the browser calls the Gateway origin directly.

Frontend environment:

```bash
NEXT_PUBLIC_BACKEND_BASE_URL="https://gateway.example.com"
NEXT_PUBLIC_LANGGRAPH_BASE_URL="https://gateway.example.com/api"
DEER_FLOW_TRUSTED_ORIGINS="https://assistant.example.com"
```

Gateway environment:

```bash
GATEWAY_CORS_ORIGINS="https://assistant.example.com"
```

`NEXT_PUBLIC_*` values are exposed to browser JavaScript and should point only
at public HTTPS origins. `GATEWAY_CORS_ORIGINS` is the Gateway allowlist used by
CORS and CSRF origin checks; do not use `*` in production.

### Harness-only SDK

Use this mode for internal Python services that need orchestration without the
Gateway or UI.

```bash
uv add deerflow-harness
```

Then import the SDK directly:

```python
from pathlib import Path

from deerflow import DeerFlowClient, load_extension_catalog

repo_root = Path("/opt/deerflow-runtime")
catalog = load_extension_catalog(
    [repo_root / "registries" / "internal_extensions.json"],
    repo_root=repo_root,
)

client = DeerFlowClient()
print(client.chat("List the enabled internal reporting capabilities."))
```

## Gateway Service

Install and start the Gateway from the backend workspace:

```bash
cd backend
uv sync --frozen
PYTHONPATH=. uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001
```

Useful Gateway environment variables:

```bash
GATEWAY_HOST="0.0.0.0"
GATEWAY_PORT="8001"
GATEWAY_ENABLE_DOCS="false"
GATEWAY_CORS_ORIGINS="https://assistant.example.com"
DEER_FLOW_CONFIG_PATH="/etc/deerflow/config.yaml"
DEER_FLOW_EXTENSIONS_CONFIG_PATH="/etc/deerflow/extensions_config.json"
DEER_FLOW_AUTH_DISABLED="0"
```

`DEER_FLOW_AUTH_DISABLED=1` is acceptable for local demos and automated smoke
tests only. Production deployments should leave authentication enabled and
configure provider credentials through the normal Gateway auth settings.

## Frontend Service

Install, build, and run the UI independently:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm build
pnpm start
```

For a container or platform build, set `NEXT_CONFIG_BUILD_OUTPUT=standalone` if
you want Next.js standalone output.

When moving the UI to a separate repository, copy only the frontend project and
keep these boundaries:

- The UI consumes the Gateway through HTTP and typed frontend helpers.
- The UI should not import Python modules or registry loader internals.
- Public browser URLs belong in `NEXT_PUBLIC_BACKEND_BASE_URL` and
  `NEXT_PUBLIC_LANGGRAPH_BASE_URL`.
- Server-only Gateway wiring belongs in `DEER_FLOW_INTERNAL_GATEWAY_BASE_URL`.

## Registry and Capability Files

Keep registry JSON and internal capability directories with the Gateway or the
runtime volume that the harness can read:

```text
/etc/deerflow/
  config.yaml
  extensions_config.json
  registries/
    internal_extensions.json
  internal_agents/
  internal_mcps/
  internal_tools/
  internal_skills/
```

Registry imports are admin-only because descriptors can reference Python
entrypoints, local skill paths, and MCP process metadata. Keep the default
manifest limits unless there is a reviewed production reason to raise them:

- 512 KiB max import payload.
- 200 descriptors per import.
- allowlisted entrypoint prefixes through
  `DEERFLOW_EXTENSION_IMPORT_ENTRYPOINT_PREFIXES`.

## Smoke Checks

Run these before a demo or deployment handoff:

```bash
cd backend
uv run pytest tests/test_harness_boundary.py -q
uv run python ../scripts/production_readiness.py
```

For the frontend:

```bash
cd frontend
pnpm typecheck
pnpm lint
pnpm test tests/unit/core/extensions/browser.test.ts tests/unit/core/threads/timeline.test.ts
```

For the full hackathon path:

```bash
cd frontend
pnpm test:e2e tests/e2e/hackathon-demo.spec.ts --project=chromium
```

## Hackathon Split Demo Bundle

Use the split demo bundle when you want a production-like local deployment
without the reverse proxy. It starts only the Next.js UI and FastAPI Gateway,
keeps the Gateway as the harness boundary, and mounts the internal capability
directories plus `registries/demo_extensions.json` into the runtime container.

Create a local env file:

```bash
cp docker/hackathon-demo.env.example docker/hackathon-demo.env
```

Set `OPENAI_API_KEY` in `docker/hackathon-demo.env` for real model calls. The
checked-in defaults keep high-risk registry extensions disabled and allow only
the demo Python function entrypoint.

Validate the bundle before a judge demo:

```bash
cd backend
uv run python ../scripts/hackathon_demo_deploy_smoke.py
```

If Docker is unavailable in CI, run the static version:

```bash
cd backend
uv run python ../scripts/hackathon_demo_deploy_smoke.py --skip-compose
```

Start the split demo:

```bash
docker compose -p deer-flow-demo \
  --env-file docker/hackathon-demo.env \
  -f docker/docker-compose.hackathon-demo.yaml up --build
```

Open the UI at `http://localhost:3000`. Gateway API docs are available at
`http://localhost:8001/api/docs` when `GATEWAY_ENABLE_DOCS=true`.

## Troubleshooting

If the UI loads but API calls fail, check whether the deployment is using
same-origin proxy mode or split-origin browser mode. In proxy mode, leave
`NEXT_PUBLIC_BACKEND_BASE_URL` unset and verify
`DEER_FLOW_INTERNAL_GATEWAY_BASE_URL`. In split-origin mode, verify both
`NEXT_PUBLIC_*` variables and `GATEWAY_CORS_ORIGINS`.

If registry capabilities do not appear, run:

```bash
cd backend
uv run python ../scripts/production_readiness.py
```

If the SDK installs but imports fail in another Python service, run:

```bash
cd backend
uv build packages/harness --wheel --out-dir dist
uv run pytest tests/test_harness_boundary.py -q
```
