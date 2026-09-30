# Skill Capabilities Guide

Skills are task-specific instruction packages. They teach the assistant how to
perform a class of work without hardcoding that workflow into the harness.

## Skill Locations

| Skill type | Location | Notes |
| --- | --- | --- |
| Internal company skills | `internal_skills/<skill-name>/SKILL.md` | Registered through extension manifests. |
| Built-in public skills | `skills/public/<skill-name>/SKILL.md` | Shipped with DeerFlow. |
| User/custom skills | Runtime skill storage | Managed by Gateway/UI skill flows. |

For this fork, internal skills stay outside `backend/packages/harness` so the
harness can remain installable as a Python dependency.

## Create an Internal Skill

Create a directory:

```text
internal_skills/customer-brief/
  SKILL.md
```

Example `SKILL.md`:

```markdown
---
name: customer-brief
description: Create concise customer context briefs from approved sources.
license: Internal
allowed-tools:
  - web_search
  - html_report
  - csv_export
---

# Customer Brief

Use this skill when the user asks for a customer, account, or opportunity
summary. Ask for the customer name and time horizon when missing. Prefer concise
sections: context, current signals, risks, recommended next actions.
```

Register it in a manifest:

```json
{
  "kind": "skill",
  "name": "customer-brief",
  "enabled": true,
  "source": "local",
  "entrypoint": "internal_skills/customer-brief",
  "description": "Create concise customer context briefs",
  "allowed_tools": ["web_search", "html-report", "csv-export"],
  "tags": ["sales", "research"],
  "risk_level": "medium",
  "display_name": "Customer Brief",
  "category": "Research"
}
```

## Skill Activation

Users can activate skills naturally through chat when the lead agent determines
the skill is relevant. Enabled registry skills also appear in the chat
composer's capability menu. Picking one inserts `/<skill-name> ` into the draft,
or the skill's `metadata.prompt_template` if it has one.

For explicit slash-style use in supported flows:

```text
/customer-brief prepare a brief for Contoso in North America
```

## Skill Design Rules

- Keep the skill focused on one workflow.
- Include when to use it and when to ask clarifying questions.
- Name expected outputs, such as memo, report, CSV, or PDF.
- List allowed tools in frontmatter and registry metadata.
- Avoid putting secrets, customer data, or environment-specific paths in
  `SKILL.md`.
- Prefer references to approved internal sources over broad open web behavior
  when the skill is for company use.

## Registry Import for Skills

External registries can include skill descriptors. Import them through
`/workspace/extensions` like any other descriptor. The import preview validates
schema, duplicate names, entrypoint path safety, source provenance, and risk
metadata before commit.

Minimal external skill descriptor:

```json
{
  "kind": "skill",
  "name": "deal-review",
  "enabled": false,
  "source": "registry",
  "entrypoint": "internal_skills/deal-review",
  "description": "Review deal health from approved CRM exports",
  "allowed_tools": ["csv-export", "html-report"],
  "risk_level": "medium",
  "display_name": "Deal Review"
}
```

## Verification

```powershell
python scripts\production_readiness.py
cd backend
uv run pytest tests/test_skills_loader.py tests/test_extensions_router.py -q
```

Then open the UI, go to `/workspace/extensions`, and confirm the skill is
enabled in the catalog.
