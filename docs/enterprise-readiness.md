# Enterprise Readiness Plan

Date: 2026-06-30
Branch: `codex/enterprise-readiness`

This plan turns the hackathon-ready DeerFlow internal assistant into an enterprise-ready platform without collapsing the clean separation between harness, gateway, UI, and internal capabilities.

## Readiness Principles

- Keep the harness SDK-shaped under `backend/packages/harness`.
- Keep internal agents, MCPs, tools, and skills outside the harness.
- Treat external registries and runtime env files as untrusted input.
- Make every production assumption executable through checks, not tribal knowledge.
- Preserve a demo profile for hackathon rehearsal while adding stricter enterprise gates.

## Phase 1: Executable Readiness Gates

- [x] Add a production readiness script with explicit `demo` and `enterprise` profiles.
- [x] Keep demo checks compatible with no-LLM smoke tests.
- [x] Add enterprise runtime checks for auth, docs, credentials, CORS, extension risk, and Python allowlists.
- [x] Support enterprise secrets supplied through the process environment or a secrets manager.
- [x] Include demo-profile readiness in `scripts/release_smoke.py`.

Verification:

```powershell
python scripts\production_readiness.py
python scripts\production_readiness.py --profile enterprise --env-file docker\hackathon-demo.env
python scripts\release_smoke.py --skip-e2e
```

For enterprise deployments, keep `docker/hackathon-demo.env` or an equivalent runtime env file free of real secrets when possible. The enterprise profile accepts `BETTER_AUTH_SECRET` and model credentials from the process environment, so a secrets manager can inject them at runtime.

## Phase 2: Registry Security

- [x] Require explicit source provenance when source allowlists are configured.
- [x] Add registry schema version negotiation and clear compatibility errors.
- [x] Add optional registry source allowlists for enterprise deployments.
- [x] Add audit rows for rejected imports, not only committed imports.

Acceptance criteria:

- Unsafe external registries fail closed before import.
- Operators can explain why a descriptor was rejected.
- Production can restrict imports to approved sources.
- Rejected import audit rows include manifest hash/size, selected keys, source identifiers, and validation messages without storing raw registry JSON.

## Phase 3: Runtime Controls

- [x] Add admin-visible readiness status for auth, model credentials, tracing, registry risk policy, and artifact storage.
- [x] Add capability-level approval policy defaults for high-risk tools.
- [x] Add retention controls for run events and generated artifacts.
- [x] Add exportable audit evidence for compliance review.

Acceptance criteria:

- Admins can see misconfiguration before users hit it.
- High-risk capability use requires intentional enablement.
- Generated data has a documented retention path.
- Compliance reviewers can download sanitized audit evidence.

### Admin Readiness Status

The gateway exposes `GET /api/readiness` for admin users. It returns an
overall status plus component rows for authentication, model credentials,
tracing, runtime registry policy, artifact storage, retention policy, and
API docs exposure.

Statuses:

- `ready`: all components are `ok`.
- `degraded`: at least one component is `warning` and none are `error`.
- `not_ready`: at least one component is `error`.

This endpoint is intentionally separate from `/health`: `/health` remains a
simple liveness probe, while `/api/readiness` is an authenticated operator view
for production configuration.

High-risk capabilities now require two explicit operator decisions before
runtime materialization: `DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS` must include
`high`, and the descriptor must include `approval.status: "approved"` unless
`DEERFLOW_EXTENSION_REQUIRE_HIGH_RISK_APPROVAL=false` is set for trusted local
development.

### Retention Controls

Run event and generated artifact retention lives in the startup-only
`run_events` config section:

```yaml
run_events:
  retention_days: 30
  artifact_retention_days: 30
```

`retention_days` deletes persisted run events older than the configured number
of days when a retention sweep runs. `artifact_retention_days` deletes generated
artifact files under DeerFlow artifact/output directories. Set either value to
`null` only when an external retention system owns that data; `/api/readiness`
reports a warning when a sweep is disabled.

The harness exposes SDK-level sweep helpers in `deerflow.retention` so gateway
jobs, deployment cron jobs, or enterprise schedulers can apply the same policy
without coupling cleanup logic to the UI.

As of 2026-09-30, nothing calls these helpers on a schedule. The Gateway only
runs its own project-trash sweep at startup, and `/api/readiness` only reports
the configured windows. A deployment that relies on these settings needs its
own job that calls `deerflow.sweep_retention_policy(...)`.

### Audit Evidence Export

The gateway exposes `GET /api/audit/evidence` for admin users. It returns a
downloadable `deerflow-audit-evidence.json` bundle with:

- `schema_version` and `generated_at` metadata.
- Source audit log path.
- Summary counts by execution status, extension name, and artifact references.
- Sanitized audit records containing descriptor metadata, input/output
  summaries, artifact paths, and errors without raw registry manifests or full
  tool payloads.

The frontend core API exposes `exportAuditEvidence()` so the UI can add a
download action without duplicating endpoint details.

## Phase 4: Deployment Hardening

- [x] Add production compose/Kubernetes guidance separate from the hackathon demo bundle.
- [x] Add health checks that cover gateway, UI, registry load, and artifact storage.
- [x] Add dependency audit commands to the release gate.
- [x] Add rollback instructions and release owner checklist.

Acceptance criteria:

- A fresh operator can deploy from docs without asking the implementation team.
- Health checks distinguish partial startup from full readiness.
- Release rollback is documented before production use.

### Production Deployment Guide

Production deployment guidance now lives in `docs/production-deployment.md`.
It is intentionally separate from the hackathon demo bundle and covers strict
runtime defaults, Docker Compose guidance, Kubernetes service boundaries,
storage/retention expectations, release validation, rollback steps, and the
release owner checklist.

### Enterprise Health Checks

Production health uses separate liveness and readiness signals:

- Gateway liveness: unauthenticated `GET /health` returns the Gateway process
  status.
- UI liveness: unauthenticated `GET /api/health` returns the frontend process
  status.
- Registry load readiness: authenticated `GET /api/readiness` includes the
  `registry_load` component, which validates configured manifests and imported
  descriptors.
- Artifact storage readiness: authenticated `GET /api/readiness` includes the
  `artifact_storage` component, which verifies the runtime artifact base
  directory is writable.

`/health` and `/api/health` prove processes are alive. `/api/readiness` is the
operator gate that distinguishes partial startup from a deployment that can
serve registry-backed chat and generated artifacts.

### Dependency Audit Gate

Dependency audit enforcement now runs as part of `scripts/release_smoke.py`.
The gate does three things:

- Exports the backend `uv.lock` with `uv export --locked` so Python dependency
  resolution cannot drift during release validation.
- Runs `pnpm audit --prod --audit-level high --json` for the frontend.
- Fails on any unapproved high/critical advisory or any approved exception past
  its expiry date.

Known frontend transitive findings are tracked in
`docs/security/dependency-audit-baseline.json` with an owner, reason, and expiry.
The baseline was written for Nextra docs-rendering dependencies that could not
be patched directly without a compatible upstream release.

**Gate status on 2026-09-30: failing.** All six baseline entries expired on
2026-08-15. Five are no longer reported by `pnpm audit`. The lodash-es entry is
still reported and now fails as expired. After the upstream sync, `pnpm audit`
also reports 12 unapproved high/critical advisories, in `next` (critical),
`vite`, `brace-expansion`, `image-size`, and `langsmith`. These need upgrades
or reviewed, short-lived exceptions before the next promotion.

New high/critical
findings must be fixed, upgraded away, or added to the baseline with an explicit
short-lived exception before a production promotion.

Optional networked Python vulnerability scanning is available for hardened
release runs:

```powershell
$env:DEERFLOW_RUN_PIP_AUDIT = "1"
python scripts\dependency_audit.py
```

### Release Operations

Rollback instructions and the release owner checklist now live in
`docs/release-operations.md`, with a structured checklist template at
`docs/templates/release-owner-checklist.json`. The runbook covers release owner
responsibilities, pre-release validation, a rollback decision tree, post-release
evidence, and communication templates.

## Current Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Demo env disables auth by default | High in production | Enterprise profile fails when `DEER_FLOW_AUTH_DISABLED` is truthy |
| API docs are useful for demos but noisy for production | Medium | Enterprise profile fails when `GATEWAY_ENABLE_DOCS` is truthy |
| External registries are code-adjacent config | High | Import guardrails, descriptor limits, prefix checks, and `DEERFLOW_EXTENSION_IMPORT_ALLOWED_SOURCES` |
| Python function execution can run arbitrary importable code | High | Allowlist-only execution and enterprise wildcard rejection |
| Retention settings are not enforced automatically | Medium | Schedule `deerflow.sweep_retention_policy` in a deployment job |
| Dependency audit baseline expired (2026-08-15) with new high/critical advisories | High | Upgrade affected frontend packages or add reviewed, short-lived exceptions |
| Model credentials may be missing until demo time | Medium | Demo profile permits no-LLM smoke; enterprise profile requires a credential |
