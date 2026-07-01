# Observability Guide

This app has three observability layers:

1. Product/runtime health for UI and Gateway.
2. Harness audit and run events for internal evidence.
3. LLM/agent tracing through LangSmith and/or Langfuse.

## Health and Readiness

Use liveness for process checks:

```powershell
curl.exe -fsS http://localhost:2026/api/health
curl.exe -fsS http://localhost:8001/health
```

Use readiness for operator checks:

```powershell
curl.exe -fsS -H "Authorization: Bearer <admin-token>" http://localhost:8001/api/readiness
```

Readiness includes authentication posture, model credentials, tracing,
registry-load status, runtime registry policy, artifact storage, retention
policy, and API docs exposure.

## Audit Evidence

Admin users can export sanitized audit evidence:

```powershell
curl.exe -fsS -H "Authorization: Bearer <admin-token>" `
  http://localhost:8001/api/audit/evidence `
  -o deerflow-audit-evidence.json
```

The export includes execution status counts, extension metadata, artifact
references, and sanitized records without raw registry manifests or full tool
payloads.

## LangSmith

Add these values to `.env`, Container Apps secrets, or your platform secret
manager:

```bash
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=<secret>
LANGSMITH_PROJECT=deerflow-internal-assistant
```

LangSmith is useful for model calls, tool traces, chain timing, and debugging
agent behavior across runs.

## Langfuse

Add:

```bash
LANGFUSE_TRACING=true
LANGFUSE_PUBLIC_KEY=<public-key>
LANGFUSE_SECRET_KEY=<secret>
LANGFUSE_BASE_URL=https://cloud.langfuse.com
DEER_FLOW_ENV=staging
```

Langfuse trace correlation fields:

| Field | Source |
| --- | --- |
| `session_id` | LangGraph `thread_id` |
| `user_id` | Effective DeerFlow user |
| `trace_name` | Assistant id |
| `tags` | `env:<DEER_FLOW_ENV>` and model tags |

If both LangSmith and Langfuse are enabled, DeerFlow attaches both callbacks.
If a provider is explicitly enabled but misconfigured, tracing initialization
fails fast and names the provider.

## Azure Observability

For Azure deployments:

- Send container stdout/stderr to Log Analytics.
- Enable Application Insights on the frontend and Gateway hosting layer.
- Keep LangSmith/Langfuse for LLM/agent traces because platform logs do not show
  model/tool reasoning chains.
- Set `DEER_FLOW_ENV=azure-staging` or `DEER_FLOW_ENV=azure-prod` so traces are
  easy to filter.
- Store LangSmith/Langfuse keys in Key Vault or Container Apps secrets.

## Demo Observability Path

For the hackathon demo:

1. Start the app.
2. Open `/workspace/extensions`.
3. Show registry health and audit rows.
4. Run a chat with `Capabilities -> Hackathon demo flow`.
5. Show the run timeline.
6. Download generated artifacts.
7. Export audit evidence if an admin token is available.

Fallback evidence screenshots are in `docs/pr-evidence/`.
