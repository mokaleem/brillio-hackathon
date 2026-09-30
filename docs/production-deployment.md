# Production Deployment Guide

This guide is for an enterprise deployment of the internal DeerFlow assistant.
The Hackathon demo bundle is not a production deployment: it intentionally keeps
auth disabled, API docs enabled, and local ports open for rehearsal. Use this
guide when the UI, Gateway, harness SDK, and internal capability registries are
operated as production services.

## Production Topology

```text
Browser
  |
  | HTTPS
  v
Frontend service or static host
  |
  | server-side proxy to /api/*
  v
Gateway API service
  |
  | Python package import
  v
deerflow-harness SDK
  |
  | read-only registry and capability mounts
  v
internal_agents/ internal_mcps/ internal_tools/ internal_skills/

Shared runtime dependencies:
  - database/checkpointer storage
  - run event store
  - generated artifact storage
  - secret manager
  - logs, metrics, and traces
```

Keep the layers independently deployable:

- The UI talks to the Gateway over HTTP only.
- The Gateway is the browser-facing trust boundary.
- The harness remains installable as a Python SDK under
  `backend/packages/harness`.
- Internal agents, MCPs, tools, and skills remain outside the harness and are
  mounted or packaged as reviewed company capabilities.
- Registry JSON is configuration input and must be treated as untrusted until
  the Gateway validates it.

## Required Runtime Settings

Production must fail closed when security-critical values are missing. Set these
through the platform secret/config system, not through checked-in env files:

```bash
DEER_FLOW_AUTH_DISABLED=0
GATEWAY_ENABLE_DOCS=false
DEER_FLOW_TRUSTED_ORIGINS=https://assistant.example.com
GATEWAY_CORS_ORIGINS=https://assistant.example.com
BETTER_AUTH_SECRET=<secret-manager-value>
OPENAI_API_KEY=<secret-manager-value>
DEERFLOW_EXTENSION_MANIFESTS=/etc/deerflow/registries/internal_extensions.json
DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS=low,medium
DEERFLOW_EXTENSION_REQUIRE_HIGH_RISK_APPROVAL=true
DEERFLOW_EXTENSION_IMPORT_ALLOWED_SOURCES=local,package
DEERFLOW_EXTENSION_IMPORT_ENTRYPOINT_PREFIXES=internal_tools.,internal_agents.,deerflow.
DEERFLOW_PYTHON_FUNCTION_ALLOWLIST=internal_tools.python_examples:summarize_metrics
DEER_FLOW_HOME=/var/lib/deerflow
```

Rules for operators:

- Do not use wildcard CORS or trusted origins.
- Do not enable `high` risk extensions by default.
- Do not use `DEERFLOW_PYTHON_FUNCTION_ALLOWLIST=*`.
- Do not expose `/api/docs`, `/docs`, `/redoc`, or `/openapi.json` in
  production.
- Store model credentials and `BETTER_AUTH_SECRET` in a secret manager.
- Mount registry and internal capability directories read-only.

## Docker Compose Guidance

Use Compose for a small internal deployment or staging environment. Keep this
separate from `docker/docker-compose.hackathon-demo.yaml`; the demo file is tuned
for judge rehearsal, not production.

Minimum service layout:

```yaml
services:
  frontend:
    image: company/deerflow-frontend:2026.07.01
    environment:
      DEER_FLOW_INTERNAL_GATEWAY_BASE_URL: http://gateway:8001
      DEER_FLOW_TRUSTED_ORIGINS: https://assistant.example.com
    ports:
      - "3000:3000"
    depends_on:
      gateway:
        condition: service_healthy

  gateway:
    image: company/deerflow-gateway:2026.07.01
    environment:
      DEER_FLOW_AUTH_DISABLED: "0"
      GATEWAY_ENABLE_DOCS: "false"
      GATEWAY_CORS_ORIGINS: https://assistant.example.com
      DEER_FLOW_HOME: /var/lib/deerflow
      DEERFLOW_EXTENSION_MANIFESTS: /etc/deerflow/registries/internal_extensions.json
      DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS: low,medium
      DEERFLOW_EXTENSION_REQUIRE_HIGH_RISK_APPROVAL: "true"
      DEERFLOW_PYTHON_FUNCTION_ALLOWLIST: internal_tools.python_examples:summarize_metrics
    env_file:
      - /run/secrets/deerflow-gateway.env
    volumes:
      - deerflow-data:/var/lib/deerflow
      - ./registries:/etc/deerflow/registries:ro
      - ./internal_agents:/app/internal_agents:ro
      - ./internal_mcps:/app/internal_mcps:ro
      - ./internal_tools:/app/internal_tools:ro
      - ./internal_skills:/app/internal_skills:ro
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=5)"]
      interval: 30s
      timeout: 5s
      retries: 3

volumes:
  deerflow-data:
```

Before promoting this shape, replace local bind mounts with immutable images,
signed artifacts, or read-only platform volumes owned by the release pipeline.

## Kubernetes Guidance

Upstream DeerFlow ships a Helm chart at `deploy/helm/deer-flow` (Gateway,
frontend, nginx, and provisioner). Start from that chart and add this fork's
registry settings, the `DEERFLOW_EXTENSION_*` variables and read-only registry
and `internal_*` mounts, through its values file. The guidance below lists
what those values need to cover.

Use separate Deployments for the UI and Gateway. Keep public ingress pointed at
the UI unless your security model requires a direct Gateway origin. In the
same-origin mode, the UI proxies `/api/*` to the internal Gateway service.

Recommended Kubernetes objects:

- `Deployment/frontend` with only UI env variables.
- `Deployment/gateway` with harness, registry, and runtime env variables.
- `Service/frontend` exposed through Ingress.
- `Service/gateway` as a cluster-internal service.
- `Secret/deerflow-gateway` for auth and model credentials.
- `ConfigMap/deerflow-registry` or read-only volume for reviewed registry JSON.
- `PersistentVolumeClaim/deerflow-data` for `DEER_FLOW_HOME`, or a configured
  platform storage path when artifacts are externalized.

Probe shape:

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8001
  periodSeconds: 10
  failureThreshold: 3
livenessProbe:
  httpGet:
    path: /health
    port: 8001
  periodSeconds: 30
  failureThreshold: 3
```

Use `/health` for unauthenticated liveness. Use authenticated
`GET /api/readiness` as the operator readiness view before opening traffic or
announcing a release. It checks auth posture, credentials, tracing, registry
load, registry policy, artifact storage, retention policy, and docs exposure.

## Storage and Data Retention

`DEER_FLOW_HOME` holds runtime data such as thread files, generated artifacts,
local stores, and service-owned secrets created by deployment scripts. In
containers, set `DEER_FLOW_HOST_BASE_DIR` only when the sandbox or artifact
delivery path must map a container path back to a host path.

Production operators must decide which layer owns retention:

- Use `run_events.retention_days` for persisted orchestration events.
- Use `run_events.artifact_retention_days` for generated artifacts.
- Set either value to `null` only when an external retention system owns the
  cleanup lifecycle.
- Confirm `GET /api/readiness` does not report retention warnings before
  release.
- Schedule the sweep yourself. The Gateway does not run run-event or artifact
  retention automatically. Run `deerflow.sweep_retention_policy(...)` from a
  Kubernetes CronJob, a scheduled container task, or a Gateway extension.

## Release Validation

Run these gates before every production promotion:

```powershell
python scripts\dependency_audit.py
python scripts\production_readiness.py
python scripts\production_readiness.py --profile enterprise --env-file path\to\enterprise.env
python scripts\release_smoke.py --skip-e2e
```

`scripts\dependency_audit.py` exports the backend lock with `uv export --locked`
and runs `pnpm audit --prod --audit-level high` against frontend production
dependencies. High/critical findings must be fixed or represented by a
short-lived entry in `docs/security/dependency-audit-baseline.json`. As of
2026-09-30 this gate fails: the baseline expired on 2026-08-15 and new advisories
are unapproved. See the Dependency Audit Gate section of
`docs/enterprise-readiness.md`. Set
`DEERFLOW_RUN_PIP_AUDIT=1` when the release environment is allowed to run the
networked Python `pip-audit` check.

Then verify the live deployment:

```powershell
curl.exe -fsS https://assistant.example.com/health
curl.exe -fsS https://assistant.example.com/api/health
curl.exe -fsS https://gateway.example.com/health
curl.exe -fsS -H "Authorization: Bearer <admin-token>" https://gateway.example.com/api/readiness
```

The first three checks prove processes are alive. The `/api/readiness` response
must be `ready` before production traffic is considered healthy.

## Rollout Procedure

Use `docs/release-operations.md` and
`docs/templates/release-owner-checklist.json` as the release record for the
promotion window.

1. Build immutable UI and Gateway images from the same commit.
2. Run unit, frontend, release smoke, and production readiness gates.
3. Publish images with a version tag and immutable digest.
4. Apply secrets and config for the target environment.
5. Deploy the Gateway first and wait for `/health`.
6. Call authenticated `/api/readiness` and resolve all `error` rows.
7. Deploy the UI and verify same-origin API calls or configured CORS.
8. Run a low-risk chat path that lists enabled registry capabilities.
9. Export audit evidence from `GET /api/audit/evidence` and attach it to the
   release record.
10. Mark the previous image digest and runtime env snapshot as the rollback
    target.

## Rollback Procedure

Rollback must be prepared before the release starts:

- Keep the previous UI and Gateway image digests available.
- Keep the previous registry manifest and runtime env snapshot.
- Avoid destructive data migrations in the same release as application code.
- If a registry import caused the issue, disable the imported descriptors or
  restore the previous registry manifest first.
- If the Gateway is unhealthy, roll back the Gateway image before rolling back
  the UI.
- If only the UI is affected, roll back the UI image while keeping the Gateway
  stable.

After rollback:

```powershell
python scripts\production_readiness.py --profile enterprise --env-file path\to\enterprise.env
curl.exe -fsS -H "Authorization: Bearer <admin-token>" https://gateway.example.com/api/readiness
```

Attach the rollback reason, image digests, registry manifest hash, readiness
output, and audit evidence bundle to the incident or release record.

## Release Owner Checklist

- [ ] Auth is enabled and API docs are disabled.
- [ ] CORS and trusted origins contain exact HTTPS origins only.
- [ ] Model credentials and auth secrets come from the secret manager.
- [ ] Registry manifests and internal capability directories are reviewed and
      mounted read-only.
- [ ] High-risk extensions require explicit descriptor approval.
- [ ] Python function execution uses an explicit allowlist.
- [ ] `DEER_FLOW_HOME` has durable storage and a documented backup policy.
- [ ] Retention settings match the company data policy.
- [ ] `/health` passes for Gateway and `/api/health` passes for UI.
- [ ] Authenticated `/api/readiness` returns `ready`.
- [ ] Rollback image digests and registry/env snapshots are recorded.
