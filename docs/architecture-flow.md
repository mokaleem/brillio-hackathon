# Architecture and Flow

The hackathon app turns DeerFlow into a company-internal assistant platform. The
important separation is:

- UI is replaceable and talks to the Gateway over HTTP.
- Gateway owns browser-facing auth, registry APIs, audit APIs, health checks,
  and LangGraph-compatible run endpoints.
- Harness remains SDK-shaped under `backend/packages/harness`.
- Internal agents, MCPs, tools, and skills live outside the harness.
- Registries are configuration data and are validated before runtime use.

## Component Diagram

```mermaid
flowchart LR
  Browser["Browser / Chat UI"]
  UI["Frontend (Next.js)"]
  Gateway["Gateway API (FastAPI)"]
  Harness["deerflow-harness SDK"]
  Registry["Registry JSON manifests"]
  Internal["internal_agents / internal_mcps / internal_tools / internal_skills"]
  Stores["Run events / audit log / artifacts / thread state"]
  Observability["LangSmith / Langfuse / platform logs"]

  Browser --> UI
  UI -->|"HTTP /api/*"| Gateway
  Gateway --> Harness
  Gateway --> Registry
  Harness --> Internal
  Harness --> Stores
  Harness --> Observability
  Gateway --> Observability
```

## Request Flow

```mermaid
sequenceDiagram
  participant User
  participant UI as Frontend UI
  participant Gateway as Gateway API
  participant Harness as Harness Runtime
  participant Registry as Extension Registry
  participant Tool as Agent/MCP/Tool/Skill
  participant Store as Events and Artifacts

  User->>UI: Send chat message
  UI->>Gateway: POST run through /api/langgraph/*
  Gateway->>Registry: Load enabled descriptors
  Gateway->>Harness: Start lead agent run
  Harness->>Tool: Materialize allowed capabilities
  Tool-->>Harness: Results and generated files
  Harness->>Store: Persist events, audit rows, artifacts
  Harness-->>Gateway: Stream thinking, tool events, final answer
  Gateway-->>UI: SSE stream and state snapshots
  UI-->>User: Timeline, artifacts, final answer
```

## Registry Import Flow

```mermaid
flowchart TD
  Admin["Admin user"]
  ImportUI["/workspace/extensions import UI"]
  Preview["Gateway preview validation"]
  AuditReject["Audit rejected import"]
  Commit["Commit selected descriptors"]
  Imported["registries/imported_extensions.json"]
  Catalog["Runtime extension catalog"]

  Admin --> ImportUI
  ImportUI --> Preview
  Preview -->|"errors"| AuditReject
  Preview -->|"valid selected descriptors"| Commit
  Commit --> Imported
  Imported --> Catalog
```

## Runtime Boundaries

| Boundary | Owner | Contract |
| --- | --- | --- |
| UI to Gateway | HTTP APIs | UI may be split into a separate codebase or deployment. |
| Gateway to harness | Python package import | Harness can be packaged as `deerflow-harness`. |
| Harness to internal capabilities | Registry descriptors and importable entrypoints | Internal code remains outside the SDK package. |
| Registry import | JSON manifest schema | Untrusted until validation passes. |
| Artifacts | Harness artifact helpers | HTML, PDF, CSV, and generated files are served through Gateway controls. |

## Health and Readiness

- UI liveness: `GET /api/health`
- Gateway liveness: `GET /health`
- Operator readiness: authenticated `GET /api/readiness`
- Release readiness: `python scripts\production_readiness.py`
- Full fast gate: `python scripts\release_smoke.py --skip-e2e`

## Why This Is Demo-Friendly

- The extension registry proves dynamic loading for agents, MCPs, tools, and
  skills.
- The capability menu gives judges a visible entry point into those dynamic
  capabilities.
- Run timeline and audit evidence prove the harness streams thinking/tool steps,
  not just final answers.
- Generated HTML, CSV, and PDF artifacts prove the assistant can perform real
  internal work.
