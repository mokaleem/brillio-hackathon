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

- [ ] Add admin-visible readiness status for auth, model credentials, tracing, registry risk policy, and artifact storage.
- [ ] Add capability-level approval policy defaults for high-risk tools.
- [ ] Add retention controls for run events and generated artifacts.
- [ ] Add exportable audit evidence for compliance review.

Acceptance criteria:

- Admins can see misconfiguration before users hit it.
- High-risk capability use requires intentional enablement.
- Generated data has a documented retention path.

## Phase 4: Deployment Hardening

- [ ] Add production compose/Kubernetes guidance separate from the hackathon demo bundle.
- [ ] Add health checks that cover gateway, UI, registry load, and artifact storage.
- [ ] Add dependency audit commands to the release gate.
- [ ] Add rollback instructions and release owner checklist.

Acceptance criteria:

- A fresh operator can deploy from docs without asking the implementation team.
- Health checks distinguish partial startup from full readiness.
- Release rollback is documented before production use.

## Current Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Demo env disables auth by default | High in production | Enterprise profile fails when `DEER_FLOW_AUTH_DISABLED` is truthy |
| API docs are useful for demos but noisy for production | Medium | Enterprise profile fails when `GATEWAY_ENABLE_DOCS` is truthy |
| External registries are code-adjacent config | High | Import guardrails, descriptor limits, prefix checks, and upcoming source allowlists |
| Python function execution is high risk | High | Allowlist-only execution and enterprise wildcard rejection |
| Model credentials may be missing until demo time | Medium | Demo profile permits no-LLM smoke; enterprise profile requires a credential |
