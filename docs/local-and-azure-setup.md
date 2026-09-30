# Local and Azure Setup

This guide is the shortest path to running the internal DeerFlow assistant
locally and the recommended shape for deploying it on Azure. It assumes the
hackathon fork layout where the UI, Gateway, harness package, registries, and
internal capabilities remain separately deployable.

## Local Setup

Prerequisites:

- Python 3.12+
- Node.js 22+
- pnpm
- uv
- Git Bash on Windows for shell-backed `make` targets
- Docker Desktop or Docker Engine when using Docker-based startup

Fast local demo:

```powershell
make demo-config
notepad .env
make doctor
make demo-smoke
make dev
```

Set at least one model credential in `.env` before real chat calls. For the
default demo path, `OPENAI_API_KEY` is enough. `make demo-smoke` does not call
an LLM; it validates the extension registry and generates sample HTML, CSV, and
PDF artifacts.

Open the app:

```text
http://localhost:2026
```

Useful local checks:

```powershell
python scripts\production_readiness.py
python scripts\dependency_audit.py
python scripts\release_smoke.py --skip-e2e
```

Docker split demo:

```powershell
Copy-Item docker\hackathon-demo.env.example docker\hackathon-demo.env
notepad docker\hackathon-demo.env
python scripts\run_hackathon_demo.py
```

This starts:

- UI at `http://localhost:3000`
- Gateway at `http://localhost:8001`

Use this mode when you want to prove the UI can run as a separate deployment
from the Gateway and harness runtime.

## Azure Deployment Shape

Recommended Azure services:

| Layer | Azure service | Notes |
| --- | --- | --- |
| Frontend | Azure Container Apps or Azure App Service for Containers | Next.js UI. Keep browser traffic pointed here. |
| Gateway | Azure Container Apps or AKS | Python Gateway API plus harness package. Start with one replica and one worker. Multiple workers or replicas need PostgreSQL plus the Redis stream bridge and run-ownership settings in `config.example.yaml`. |
| Images | Azure Container Registry | Store immutable frontend and Gateway images. |
| Secrets | Azure Key Vault | Store model keys, auth secrets, LangSmith/Langfuse keys, and registry source secrets. |
| Storage | Azure Files, Azure Blob, or mounted persistent volume | Back `DEER_FLOW_HOME`, generated artifacts, and run event storage. |
| Identity | Microsoft Entra ID OIDC | Configure through DeerFlow SSO settings when auth is enabled. |
| Observability | Application Insights plus LangSmith or Langfuse | App health/logs in Azure; agent traces in LangSmith/Langfuse. |

Minimum production environment posture:

```bash
DEER_FLOW_AUTH_DISABLED=0
GATEWAY_ENABLE_DOCS=false
DEER_FLOW_TRUSTED_ORIGINS=https://assistant.example.com
GATEWAY_CORS_ORIGINS=https://assistant.example.com
BETTER_AUTH_SECRET=<key-vault-secret>
OPENAI_API_KEY=<key-vault-secret>
DEERFLOW_EXTENSION_MANIFESTS=/etc/deerflow/registries/internal_extensions.json
DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS=low,medium
DEERFLOW_EXTENSION_REQUIRE_HIGH_RISK_APPROVAL=true
DEERFLOW_PYTHON_FUNCTION_ALLOWLIST=internal_tools.python_examples:summarize_metrics
DEER_FLOW_HOME=/var/lib/deerflow
```

## Azure Container Apps Outline

Build and push images to Azure Container Registry:

```powershell
$resourceGroup = "rg-deerflow-demo"
$location = "eastus"
$acrName = "deerflowdemoacr"

az group create --name $resourceGroup --location $location
az acr create --resource-group $resourceGroup --name $acrName --sku Basic
az acr login --name $acrName

$registry = "$acrName.azurecr.io"
docker build -t "$registry/deerflow-frontend:demo" -f frontend/Dockerfile .
docker build -t "$registry/deerflow-gateway:demo" -f backend/Dockerfile .
docker push "$registry/deerflow-frontend:demo"
docker push "$registry/deerflow-gateway:demo"
```

Create a Container Apps environment and apps:

```powershell
$envName = "cae-deerflow-demo"
az containerapp env create `
  --name $envName `
  --resource-group $resourceGroup `
  --location $location

az containerapp create `
  --name deerflow-gateway `
  --resource-group $resourceGroup `
  --environment $envName `
  --image "$registry/deerflow-gateway:demo" `
  --target-port 8001 `
  --ingress internal `
  --env-vars `
    DEER_FLOW_AUTH_DISABLED=0 `
    GATEWAY_ENABLE_DOCS=false `
    DEER_FLOW_PROJECT_ROOT=/app `
    DEER_FLOW_HOME=/var/lib/deerflow `
    DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS=low,medium `
    DEERFLOW_EXTENSION_REQUIRE_HIGH_RISK_APPROVAL=true

az containerapp create `
  --name deerflow-frontend `
  --resource-group $resourceGroup `
  --environment $envName `
  --image "$registry/deerflow-frontend:demo" `
  --target-port 3000 `
  --ingress external `
  --env-vars `
    DEER_FLOW_INTERNAL_GATEWAY_BASE_URL=http://deerflow-gateway `
    DEER_FLOW_TRUSTED_ORIGINS=https://assistant.example.com
```

For production, do not paste real secrets into command history. Bind Container
Apps secrets to Key Vault-backed values and reference them in app env vars.

## Azure Readiness Validation

Before routing users:

```powershell
python scripts\dependency_audit.py
python scripts\production_readiness.py --profile enterprise --env-file path\to\enterprise.env
python scripts\release_smoke.py --skip-e2e
```

After deploy:

```powershell
curl.exe -fsS https://assistant.example.com/api/health
curl.exe -fsS https://gateway.example.com/health
curl.exe -fsS -H "Authorization: Bearer <admin-token>" https://gateway.example.com/api/readiness
```

Record image digests, registry manifest hash, runtime env/secret versions, and
rollback targets using `docs/templates/release-owner-checklist.json`.
