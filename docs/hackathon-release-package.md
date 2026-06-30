# Hackathon Release Package

Date: 2026-06-30
Branch: `dev`
Pull request: https://github.com/mokaleem/brillio-hackathon/pull/1
Head commit: `ebba959e`
Status: Draft PR, mergeable, Hackathon Quality Gate green.

This package is the ready-to-share PR and release brief for the internal DeerFlow assistant demo. It is scoped to the configurable harness, dynamic capability registry, separated UI layer, and hackathon judge path.

## Draft PR

Title:

```text
Build internal mini ChatGPT capability platform on DeerFlow
```

Body:

```markdown
## Summary

- Adds a loosely coupled extension registry for agents, MCPs, tools, and skills with local and external manifest support.
- Keeps harness/SDK, gateway APIs, UI, and internal company capabilities separated so the UI or harness can move to separate deployables.
- Adds admin registry management: validation, health, import preview, import commit, imported-capability removal, dependency-gated enablement, and runtime observability.
- Streams and persists orchestration trace/audit context so the UI can show thinking/tool progress plus final answers and generated artifacts.
- Provides a one-command hackathon demo launcher, split deployment bundle, demo smoke scripts, and judge walkthrough docs.

## Demo Path

1. Start the demo with `uv run python ../scripts/run_hackathon_demo.py --no-start` from `backend/`, or run the full Docker launcher when Docker is available.
2. Open `/workspace/extensions`.
3. Show `Demo Observability`, registry health, execution audit, and capability configuration.
4. Import a registry descriptor through `Import -> Preview -> Import Selected`.
5. Remove the imported descriptor through `Remove import` to demonstrate rollback.
6. Open `/workspace/chats/new`, choose `Capabilities -> Hackathon demo flow`, and send the prompt.
7. Show generated HTML, CSV, PDF, Python execution result, run trace, and audit rows.

## Verification

- Full release gate: `make release-smoke`
- Fast release gate without Chromium E2E: `python scripts/release_smoke.py --skip-e2e`
- GitHub Actions `Hackathon Quality Gate` on `ebba959e`: `Backend Readiness`, `Frontend Quality`, and `Demo E2E` passed.
- `uv run pytest tests/test_audit_router.py -q`
- `uv run pytest tests/test_extensions_router.py -q`
- `uv run ruff format --check .`
- `uv run ruff check app\gateway\routers\audit.py app\gateway\routers\extensions.py app\gateway\app.py app\gateway\routers\__init__.py tests\test_audit_router.py tests\test_extensions_router.py`
- `pnpm test tests/unit/core/audit/api.test.ts`
- `pnpm test tests/unit/core/extensions/api.test.ts`
- `pnpm typecheck`
- `pnpm lint`
- `pnpm test:e2e tests/e2e/hackathon-demo.spec.ts --project=chromium --reporter=list`

## Known Warnings

- No known lint or Turbopack warnings in the release gate as of `dev`.
```

## Evidence Screenshots

- `docs/pr-evidence/hackathon-extension-registry.png` - loaded registry, health, audit, and configuration controls.
- `docs/pr-evidence/hackathon-demo-observability.png` - demo readiness, executions, artifacts, registry-sourced entries, and risk signal.
- `docs/pr-evidence/hackathon-import-preview.png` - external registry preview before commit.
- `docs/pr-evidence/hackathon-chat-capabilities.png` - chat capability picker with the hackathon demo prompt.
- `docs/pr-evidence/hackathon-run-trace.png` - persisted run timeline and capability audit rows.
- `docs/pr-evidence/hackathon-artifact-center.png` - generated HTML, CSV, and PDF artifact center.

## Release Checklist

- [x] Dynamic agents, MCPs, tools, and skills can be loaded from manifests/registries.
- [x] Internal company capabilities live outside the harness under `internal_agents/`, `internal_mcps/`, `internal_tools/`, and `internal_skills/`.
- [x] Harness package remains SDK-shaped under `backend/packages/harness`.
- [x] UI consumes typed gateway APIs and can be separated from the backend codebase.
- [x] External registry import supports preview, safety validation, duplicate detection, provenance stamping, and selected import.
- [x] Imported registry entries can be removed without mutating base manifests.
- [x] Capability enablement validates required dependencies before activation.
- [x] Runtime tool execution writes audit rows and exposes them through an admin API.
- [x] Extension Registry UI shows health, configuration, execution audit, and demo observability.
- [x] Chat capability picker includes a one-click hackathon demo prompt and high-risk approval flow.
- [x] Harness can generate HTML, PDF, CSV, and allowlisted Python execution outputs.
- [x] Split deploy and one-command demo launcher docs/scripts are present.

## Commit Spine

- `ebba959e` - backend format gate aligned with CI.
- `4be14f76` - hackathon release smoke gate.
- `b7ebbc8d` - PR evidence screenshots.
- `3456c1d9` - mock artifact tracing scope fix.
- `3c80da73` - frontend lint warning cleanup.
- `f54960f3` - release package.
- `38585e5e` - demo observability panel.
- `4961ffea` - dependency validation before capability enablement.
- `b950a874` - remove imported registry capabilities.
- `3ccc970e` - execution audit viewer.
- `5b93be6d` - one-command hackathon demo launcher.
- `b9aa987d` - runtime audit for registry tool execution.
- `d3839594` - registry import diff preview.
- `da9491ae` - capability configuration controls.
- `d79d0ea9` - split demo deploy bundle.
- `6969383a` - registry import provenance.

## Release Notes

This release turns the DeerFlow fork into a company-internal assistant platform. The important architectural choice is that registry descriptors are data, internal capabilities are outside the harness, and the UI only talks through gateway contracts. That keeps the hackathon demo impressive while preserving the option to package the harness as a Python dependency or host the UI separately.
