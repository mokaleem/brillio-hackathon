# Hackathon Judge Runbook

Use this as the five-minute rehearsal script for the internal assistant demo. The original feature work landed in PR #1 (merged 2026-06-30). Keep the browser at 1440px width if possible, use `/workspace/extensions` first, and keep `docs/pr-evidence/` open as fallback proof if the live stack is slow.

## Preflight

```powershell
python scripts\release_smoke.py --skip-e2e
cd frontend
pnpm test:e2e tests/e2e/hackathon-demo.spec.ts --project=chromium --reporter=list
```

Confirm:

- The latest `Hackathon Quality Gate` run on `dev` is green.
- `.env` or `docker/hackathon-demo.env` has the model key for live chat.
- Evidence screenshots are present under `docs/pr-evidence/`.

## Five-Minute Script

### 0:00-0:30 - Frame The Platform

Open `/workspace/extensions`.

Say:

> We turned DeerFlow into a configurable internal ChatGPT platform. The harness stays SDK-shaped, the UI talks through gateway APIs, and company-owned agents, MCPs, tools, and skills live outside the harness.

Point at:

- `Extension Registry` page title.
- Sidebar `Extensions` navigation.
- `Demo Observability` strip.

Fallback screenshot: `docs/pr-evidence/hackathon-extension-registry.png`

### 0:30-1:20 - Prove Dynamic Capability Loading

On `/workspace/extensions`, show:

- Registry health and manifest path.
- Capability counts for agents, MCPs, tools, and skills.
- `Reporting Agent`, `HTML Report`, `CSV Export`, `PDF Report`, and `Python Function`.

Say:

> These entries are descriptors, not hardcoded UI branches. They can come from local manifests or imported registries, and enablement is guarded by dependency validation.

Fallback screenshot: `docs/pr-evidence/hackathon-demo-observability.png`

### 1:20-2:10 - Show Registry Import And Rollback

Click `Import`, paste a registry descriptor, then click `Preview`.

Say:

> Imports are admin-only and fail closed. Preview shows duplicates, risk, source, and safety warnings before anything is enabled.

If already imported, show `Remove import` on the imported row.

Fallback screenshot: `docs/pr-evidence/hackathon-import-preview.png`

### 2:10-3:10 - Launch The Chat Demo

Open `/workspace/chats/new`, click `Capabilities`, choose `Hackathon demo flow`.

Say:

> The chatbot can interact with registered agents, tools, and skills from one surface. High-risk capabilities require approval before insertion.

Send the prompt if model credentials are available.

Fallback screenshot: `docs/pr-evidence/hackathon-chat-capabilities.png`

### 3:10-4:10 - Show Thinking, Audit, And Artifacts

Open the chat `Trace` button.

Say:

> The harness streams orchestration activity to the UI. Final answers are not the only artifact; thinking steps, tool events, and capability audit rows are available for review and export.

Open `Artifact Center`.

Say:

> The harness can generate HTML, CSV, PDF, and allowlisted Python function outputs.

Fallback screenshots:

- `docs/pr-evidence/hackathon-run-trace.png`
- `docs/pr-evidence/hackathon-artifact-center.png`

### 4:10-5:00 - Close With Architecture

Open `docs/hackathon-release-package.md` or keep the registry page visible.

Say:

> The important design choice is separation. The harness can ship as a Python dependency, the UI can move to a separate codebase, and internal capabilities remain outside the harness. The registry contract is the glue.

Mention:

- `backend/packages/harness`
- `internal_agents/`, `internal_mcps/`, `internal_tools/`, `internal_skills/`
- `registries/demo_extensions.json`
- `docs/extension-registry-schema.md`

## Recovery Commands

If the live app is slow:

```powershell
cd frontend
pnpm test:e2e tests/e2e/hackathon-evidence.spec.ts --project=chromium --reporter=list
```

If backend registry behavior is challenged:

```powershell
cd backend
uv run pytest tests/test_audit_router.py tests/test_extensions_router.py tests/test_demo_smoke.py -q
uv run ruff format --check .
```

If artifact generation is challenged:

```powershell
cd backend
uv run python ../scripts/demo_smoke.py
```

If CI status is challenged:

```powershell
gh run list --repo mokaleem/brillio-hackathon --workflow "Hackathon Quality Gate" --branch dev --limit 5
```

## Risk Notes

- External registry JSON is code-adjacent configuration; keep production allowlists narrow.
- The Python function tool is registered as `medium` risk and can only call functions listed in `DEERFLOW_PYTHON_FUNCTION_ALLOWLIST`.
- Evidence screenshots are not a substitute for the live flow, but they keep the pitch resilient if model credentials or Docker are unavailable.
