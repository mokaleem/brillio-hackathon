# Release Operations Runbook

This runbook is for the release owner promoting the internal DeerFlow assistant
to staging or production. It complements `docs/production-deployment.md` with a
repeatable operating procedure, rollback decision tree, and evidence checklist.

## Release Owner Role

The release owner is accountable for one promotion window. They do not need to
be the only person deploying the system, but they own the release record and
make the go/no-go decision.

Responsibilities:

- Confirm the commit, image digests, registry manifest hash, and runtime env
  snapshot before opening the release window.
- Confirm `python scripts\release_smoke.py --skip-e2e` and required CI checks
  passed on the exact commit being promoted.
- Confirm production readiness with the target runtime env file or platform
  injected secrets.
- Confirm rollback targets are known before traffic shifts.
- Capture release evidence and post-release health checks.

## Pre-Release Checklist

Use `docs/templates/release-owner-checklist.json` as the structured release
record. At minimum, fill these fields before deployment starts:

- `release.owner`
- `release.environment`
- `release.commit`
- `artifacts.frontend_image_digest`
- `artifacts.gateway_image_digest`
- `artifacts.registry_manifest_sha256`
- `rollback.previous_frontend_image_digest`
- `rollback.previous_gateway_image_digest`
- `rollback.previous_registry_manifest_sha256`

Required local validation:

```powershell
python scripts\dependency_audit.py
python scripts\production_readiness.py
python scripts\production_readiness.py --profile enterprise --env-file path\to\enterprise.env
python scripts\release_smoke.py --skip-e2e
```

Required live validation:

```powershell
curl.exe -fsS https://assistant.example.com/api/health
curl.exe -fsS https://gateway.example.com/health
curl.exe -fsS -H "Authorization: Bearer <admin-token>" https://gateway.example.com/api/readiness
```

Go/no-go rule: do not open production traffic unless `/api/readiness` reports
`ready` and the release owner has a rollback target for UI, Gateway, registry,
and runtime env.

## Rollback Decision Tree

Start with the smallest safe rollback that restores service:

1. Registry import or capability failure:
   Restore the previous registry manifest or disable the imported descriptors.
   Re-run authenticated `/api/readiness` and a low-risk chat path.

2. Gateway health or orchestration failure:
   Roll back the Gateway image to the recorded digest. Keep the UI stable unless
   UI/API compatibility changed in the same release.

3. UI-only regression:
   Roll back the frontend image or static deployment while leaving the Gateway
   and registry unchanged.

4. Secret/config regression:
   Restore the previous runtime env or secret version. Restart only the service
   that consumes the changed config.

5. Data or migration issue:
   Stop the rollout, disable traffic if needed, and escalate to the data owner.
   Do not run destructive manual fixes without an incident record.

Rollback validation:

```powershell
python scripts\production_readiness.py --profile enterprise --env-file path\to\enterprise.env
curl.exe -fsS https://assistant.example.com/api/health
curl.exe -fsS https://gateway.example.com/health
curl.exe -fsS -H "Authorization: Bearer <admin-token>" https://gateway.example.com/api/readiness
```

## Post-Release Evidence

Attach these items to the release record:

- CI run URL and local release smoke output.
- Dependency audit output, including any baselined advisory IDs.
- Gateway `/health`, UI `/api/health`, and admin `/api/readiness` responses.
- Audit evidence export from `GET /api/audit/evidence`.
- Frontend and Gateway image digests.
- Registry manifest SHA-256.
- Runtime env or secret version identifiers.
- Rollback target digests and manifest hash.

## Communication Template

Release start:

```text
Starting DeerFlow internal assistant release <version> to <environment>.
Owner: <name>
Commit: <sha>
Rollback target: UI <digest>, Gateway <digest>, registry <sha256>
```

Release complete:

```text
Completed DeerFlow internal assistant release <version> to <environment>.
Health: UI /api/health PASS, Gateway /health PASS, /api/readiness ready
Evidence: <release-record-link>
```

Rollback:

```text
Rolling back DeerFlow internal assistant release <version> in <environment>.
Reason: <short reason>
Rollback target: UI <digest>, Gateway <digest>, registry <sha256>
Owner: <name>
```
