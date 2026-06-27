# Internal Mini ChatGPT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular internal mini ChatGPT platform on DeerFlow with dynamic agents, MCPs, tools, skills, streaming progress events, and report artifact generation.

**Architecture:** Keep `backend/packages/harness` as the reusable SDK. Add pure extension catalog and artifact-generation modules there, expose them through Gateway APIs later, and keep internal extension samples plus registry manifests outside the harness.

**Tech Stack:** Python 3.12, Pydantic, DeerFlow harness, FastAPI Gateway, pytest, Next.js 16, React 19, TypeScript.

---

## File Structure
- Create `backend/packages/harness/deerflow/extensions/descriptors.py`: Pydantic descriptor models for extension manifests.
- Create `backend/packages/harness/deerflow/extensions/manifest.py`: JSON loading and validation.
- Create `backend/packages/harness/deerflow/extensions/loader.py`: catalog aggregation and query API.
- Create `backend/packages/harness/deerflow/extensions/__init__.py`: public SDK exports.
- Create `backend/packages/harness/deerflow/artifacts/generators.py`: HTML, CSV, and PDF artifact helpers.
- Create `backend/tests/test_extension_registry.py`: focused pure unit tests.
- Create `backend/tests/test_artifact_generators.py`: focused pure unit tests.
- Create `internal_agents/`, `internal_mcps/`, `internal_tools/`, `internal_skills/`: company extension homes outside the harness.
- Create `registries/internal_extensions.example.json`: example manifest importing internal extension homes.
- Modify `backend/AGENTS.md`: document the extension registry architecture.
- Modify `README.md`: add user-facing hackathon extension overview.

## Task 1: Registry Descriptors

**Files:**
- Create: `backend/packages/harness/deerflow/extensions/descriptors.py`
- Create: `backend/packages/harness/deerflow/extensions/__init__.py`
- Test: `backend/tests/test_extension_registry.py`

- [ ] **Step 1: Write failing descriptor tests**

```python
from pathlib import Path

import pytest

from deerflow.extensions import ExtensionKind, ExtensionManifest, ExtensionSource


def test_manifest_parses_minimal_tool_descriptor():
    manifest = ExtensionManifest.model_validate(
        {
            "version": 1,
            "extensions": [
                {
                    "kind": "tool",
                    "name": "html_report",
                    "enabled": True,
                    "source": "local",
                    "entrypoint": "internal_tools.reporting:html_report_tool",
                    "description": "Generate HTML reports",
                }
            ],
        }
    )

    extension = manifest.extensions[0]
    assert extension.kind is ExtensionKind.TOOL
    assert extension.source is ExtensionSource.LOCAL
    assert extension.name == "html_report"
    assert extension.entrypoint == "internal_tools.reporting:html_report_tool"


def test_descriptor_rejects_invalid_name():
    with pytest.raises(ValueError, match="hyphen-case"):
        ExtensionManifest.model_validate(
            {
                "version": 1,
                "extensions": [
                    {
                        "kind": "tool",
                        "name": "Bad Name",
                        "source": "local",
                        "entrypoint": "internal_tools.reporting:html_report_tool",
                    }
                ],
            }
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_extension_registry.py -v`
Expected: FAIL because `deerflow.extensions` does not exist.

- [ ] **Step 3: Implement descriptor models**

Define `ExtensionKind`, `ExtensionSource`, `RegistryImport`, `ExtensionDescriptor`, and `ExtensionManifest` with deterministic validation and safe defaults.

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_extension_registry.py -v`
Expected: PASS for descriptor tests.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/extensions backend/tests/test_extension_registry.py
git commit -m "feat: add extension registry descriptors"
```

## Task 2: Manifest Loader and Catalog

**Files:**
- Create: `backend/packages/harness/deerflow/extensions/manifest.py`
- Create: `backend/packages/harness/deerflow/extensions/loader.py`
- Modify: `backend/packages/harness/deerflow/extensions/__init__.py`
- Modify: `backend/tests/test_extension_registry.py`

- [ ] **Step 1: Add failing loader tests**

Cover loading JSON files, resolving relative import paths under repo root, rejecting duplicate `(kind, name)` pairs, filtering enabled extensions, and failing closed on missing files.

- [ ] **Step 2: Run focused test**

Run: `cd backend && uv run pytest tests/test_extension_registry.py -v`
Expected: FAIL because loader functions are missing.

- [ ] **Step 3: Implement pure loader**

Expose `load_extension_manifest(path)` and `load_extension_catalog(paths, repo_root=...)`.

- [ ] **Step 4: Run focused test**

Run: `cd backend && uv run pytest tests/test_extension_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/extensions backend/tests/test_extension_registry.py
git commit -m "feat: load extension manifests into a catalog"
```

## Task 3: Internal Directories and Example Registry

**Files:**
- Create: `internal_agents/README.md`
- Create: `internal_mcps/README.md`
- Create: `internal_tools/README.md`
- Create: `internal_skills/README.md`
- Create: `registries/internal_extensions.example.json`
- Create: `registries/external_registries.example.json`

- [ ] **Step 1: Add examples**

Create directory READMEs and example manifests that show local extension imports and future external registry declarations.

- [ ] **Step 2: Validate manifest with tests**

Run: `cd backend && uv run pytest tests/test_extension_registry.py -v`
Expected: PASS, including loading `../registries/internal_extensions.example.json`.

- [ ] **Step 3: Commit**

```bash
git add internal_agents internal_mcps internal_tools internal_skills registries backend/tests/test_extension_registry.py
git commit -m "docs: add internal extension registry examples"
```

## Task 4: Artifact Generators

**Files:**
- Create: `backend/packages/harness/deerflow/artifacts/generators.py`
- Create: `backend/packages/harness/deerflow/artifacts/__init__.py`
- Test: `backend/tests/test_artifact_generators.py`

- [ ] **Step 1: Write failing artifact tests**

Test self-contained HTML output, CSV header/row rendering, and PDF generation fallback that either writes a minimal PDF or raises a clear dependency error.

- [ ] **Step 2: Run focused test**

Run: `cd backend && uv run pytest tests/test_artifact_generators.py -v`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement artifact helpers**

Expose `generate_html_report`, `generate_csv_file`, and `generate_pdf_report` as pure file-writing helpers.

- [ ] **Step 4: Run focused test**

Run: `cd backend && uv run pytest tests/test_artifact_generators.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/artifacts backend/tests/test_artifact_generators.py
git commit -m "feat: add report artifact generators"
```

## Task 5: Gateway Catalog API

**Files:**
- Create: `backend/app/gateway/routers/extensions.py`
- Modify: `backend/app/gateway/app.py`
- Test: `backend/tests/test_extensions_router.py`

- [ ] **Step 1: Write router tests**

Test `GET /api/extensions` returns grouped extensions, and query `?kind=tool` filters by kind.

- [ ] **Step 2: Implement router**

Use the harness catalog loader only; do not duplicate parsing in `app.*`.

- [ ] **Step 3: Run router tests**

Run: `cd backend && uv run pytest tests/test_extensions_router.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/gateway/routers/extensions.py backend/app/gateway/app.py backend/tests/test_extensions_router.py
git commit -m "feat: expose extension catalog through gateway"
```

## Task 6: UI Extension Browser

**Files:**
- Create: `frontend/src/core/extensions/api.ts`
- Create: `frontend/src/core/extensions/types.ts`
- Create: `frontend/src/components/workspace/extensions/extension-browser.tsx`
- Modify: appropriate workspace settings/navigation component after inspection.
- Test: `frontend/tests/unit/core/extensions/api.test.ts`

- [ ] **Step 1: Add frontend unit tests**

Mock `/api/extensions` and assert grouped extension data is fetched and typed.

- [ ] **Step 2: Implement API client and browser component**

Keep UI replaceable; it consumes backend JSON only.

- [ ] **Step 3: Run frontend checks**

Run: `cd frontend && pnpm test && pnpm check`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/core/extensions frontend/src/components/workspace/extensions frontend/tests/unit/core/extensions
git commit -m "feat: add extension browser UI"
```

## Task 7: Streaming Event Contract

**Files:**
- Create: `contracts/orchestration-events.schema.json`
- Modify: `backend/packages/harness/deerflow/runtime/stream_bridge/`
- Modify: frontend thread stream parser after inspection.
- Tests: backend stream bridge tests and frontend stream-mode tests.

- [ ] **Step 1: Define event schema**

Support `thinking`, `progress`, `tool_call`, `agent_handoff`, `skill_activation`, `artifact`, `final_answer`, and `error`.

- [ ] **Step 2: Preserve existing stream behavior**

Map new events into `custom` payloads so existing LangGraph messages still work.

- [ ] **Step 3: Verify both sides**

Run backend and frontend focused tests.

- [ ] **Step 4: Commit**

```bash
git add contracts backend/packages/harness/deerflow/runtime frontend/src
git commit -m "feat: add orchestration event stream contract"
```

## Task 8: Final Verification and Push

- [ ] **Step 1: Run backend focused suites**

Run: `cd backend && uv run pytest tests/test_extension_registry.py tests/test_artifact_generators.py tests/test_harness_boundary.py -v`
Expected: PASS.

- [ ] **Step 2: Run formatting/lint checks**

Run: `cd backend && make lint`
Expected: PASS or report actionable existing violations.

- [ ] **Step 3: Run frontend checks after UI changes**

Run: `cd frontend && pnpm test && pnpm check`
Expected: PASS.

- [ ] **Step 4: Push branch**

Run: `git push -u origin codex/internal-mini-chatgpt`
Expected: branch pushed to `mokaleem/brillio-hackathon`.

