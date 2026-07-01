# 15 Slide Presentation Deck Outline

Use this as the source outline for a 15 slide hackathon or executive demo deck.

## Slide 1: Title

Title: Internal Mini ChatGPT on DeerFlow

Message: A configurable enterprise assistant platform with dynamic agents,
tools, MCPs, skills, observability, and deployable UI/Gateway boundaries.

Visual: Product screenshot or extension registry screenshot.

## Slide 2: Business Problem

Message: Internal teams need a governed assistant that can use company tools,
generate artifacts, and expose audit evidence without hardcoding every workflow.

Talk track: Position this as promotion/bonus-worthy because it is not a toy
chatbot; it is a reusable internal platform.

## Slide 3: What We Built

Message: A mini ChatGPT for company use, built on DeerFlow, with dynamic
capability loading and enterprise readiness gates.

Bullets:

- Chat UI with capability picker
- Dynamic registry for agents, MCPs, tools, skills
- Artifact generation: HTML, CSV, PDF
- Run timeline and audit evidence
- Split UI/Gateway deployment support

## Slide 4: Architecture

Message: Clean separation makes it extensible.

Visual: Use the component diagram from `docs/architecture-flow.md`.

Key line: UI can be separated; harness can be packaged as an SDK; internal
capabilities live outside the harness.

## Slide 5: Dynamic Capability Registry

Message: Capabilities are data-driven through JSON manifests.

Demo proof:

- `registries/demo_extensions.json`
- `/workspace/extensions`
- Import preview and validation

## Slide 6: Agents

Message: Internal agents can be added as importable factories under
`internal_agents/`.

Example: `reporting-agent` coordinates report/export workflows.

## Slide 7: Tools and Artifacts

Message: Tools perform useful work and generate downloadable artifacts.

Examples:

- HTML report
- CSV export
- PDF report
- Allowlisted Python function execution

## Slide 8: MCP Integration

Message: MCP descriptors can be loaded dynamically from the same registry model.

Example: stdio MCP descriptor for local/internal document search.

## Slide 9: Skills

Message: Skills give the assistant reusable task-specific workflows without
hardcoding behavior into the harness.

Example: `internal_skills/market-research/SKILL.md`.

## Slide 10: User Experience

Message: The chatbot hides complexity while still surfacing power.

Demo:

- Open chat
- Click Capabilities
- Choose Hackathon demo flow
- Show run timeline and generated artifacts

## Slide 11: Governance and Safety

Message: Enterprise posture is built into the platform.

Bullets:

- Admin-only registry import
- Schema validation
- Risk levels
- High-risk approval policy
- Python allowlist
- Audit rows for rejected imports

## Slide 12: Observability

Message: Operators can trace what happened.

Bullets:

- Run events
- Audit evidence export
- LangSmith/Langfuse tracing
- UI/Gateway health and readiness

## Slide 13: Deployment

Message: Local, Docker, split deployment, and Azure-ready topology.

Talk track:

- UI and Gateway can deploy separately
- Harness remains SDK-shaped
- Azure Container Apps/AKS path is straightforward

## Slide 14: Readiness Evidence

Message: This is tested like a product.

Evidence:

- `python scripts\production_readiness.py`
- `python scripts\dependency_audit.py`
- `python scripts\release_smoke.py --skip-e2e`
- GitHub CI checks

## Slide 15: Roadmap and Ask

Message: Ready for demo; next step is company integration.

Next steps:

- Add company SSO and production secrets
- Connect real internal MCPs
- Add approved business-domain skills
- Deploy to Azure staging
- Pilot with one internal team

Close: This is a governed assistant platform, not a one-off hackathon demo.
