from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


REQUIRED_DEMO_TOOLS = {"html-report", "csv-export", "pdf-report", "python-function"}
VALID_KINDS = {"agent", "mcp", "tool", "skill"}
VALID_SOURCES = {"local", "registry", "package", "url"}
VALID_RISK_LEVELS = {"low", "medium", "high"}
EXTENSION_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MODEL_CREDENTIAL_ENV_VARS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "AZURE_OPENAI_API_KEY",
)
PLACEHOLDER_AUTH_SECRET = "replace-with-a-long-random-demo-secret"
TRUTHY_VALUES = {"1", "true", "yes", "on"}


def run_readiness_checks(
    project_root: Path = REPO_ROOT,
    *,
    profile: Literal["demo", "enterprise"] = "demo",
    env_file: Path | None = None,
) -> list[CheckResult]:
    root = project_root.resolve(strict=False)
    results: list[CheckResult] = []
    results.append(_check_required_paths(root))
    results.append(_check_demo_registry(root))
    results.append(_check_import_guardrails(root))
    results.append(_check_admin_readiness_endpoint(root))
    results.append(_check_runtime_approval_policy(root))
    results.append(_check_generated_registry_gitignored(root))
    results.append(_check_frontend_env_example(root))
    results.append(_check_demo_docs(root))
    results.append(_check_demo_deploy_bundle(root))
    if profile == "enterprise":
        results.append(_check_enterprise_runtime_env(root, env_file))
    return results


def _check_required_paths(root: Path) -> CheckResult:
    required = [
        root / "backend" / "packages" / "harness",
        root / "frontend",
        root / "internal_agents",
        root / "internal_mcps",
        root / "internal_tools",
        root / "internal_skills",
        root / "registries" / "demo_extensions.json",
        root / "docs" / "extension-registry-schema.md",
    ]
    missing = [
        path.relative_to(root).as_posix() for path in required if not path.exists()
    ]
    return CheckResult(
        "required paths",
        not missing,
        "all expected harness/UI/internal registry paths exist"
        if not missing
        else "missing: " + ", ".join(missing),
    )


def _check_demo_registry(root: Path) -> CheckResult:
    manifest = root / "registries" / "demo_extensions.json"
    errors, payload = _read_manifest(manifest)
    if errors:
        return CheckResult("demo registry", False, "; ".join(errors))
    extensions = payload.get("extensions", [])
    imports = payload.get("imports", [])
    errors = [*_validate_imports(root, imports), *_validate_extensions(extensions)]
    if errors:
        return CheckResult("demo registry", False, "; ".join(errors[:3]))

    enabled_agents = {
        extension["name"]
        for extension in extensions
        if extension.get("kind") == "agent" and extension.get("enabled") is True
    }
    enabled_tools = {
        extension["name"]
        for extension in extensions
        if extension.get("kind") == "tool" and extension.get("enabled") is True
    }
    missing_tools = sorted(REQUIRED_DEMO_TOOLS - enabled_tools)
    if "reporting-agent" not in enabled_agents:
        return CheckResult("demo registry", False, "reporting-agent is not enabled")
    if missing_tools:
        return CheckResult(
            "demo registry", False, "missing enabled tools: " + ", ".join(missing_tools)
        )
    return CheckResult(
        "demo registry",
        True,
        f"{len(extensions)} descriptors valid; enabled tools: {', '.join(sorted(enabled_tools))}",
    )


def _read_manifest(path: Path) -> tuple[list[str], dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path.name} has invalid JSON: {exc.msg}"], {}
    if not isinstance(payload, dict):
        return [f"{path.name} must contain a JSON object"], {}
    return [], payload


def _validate_imports(root: Path, imports: object) -> list[str]:
    if not isinstance(imports, list):
        return ["imports must be an array"]
    errors: list[str] = []
    for item in imports:
        if not isinstance(item, dict):
            errors.append("registry import entries must be objects")
            continue
        name = item.get("name")
        kind = item.get("kind")
        path = item.get("path")
        if not isinstance(name, str) or not EXTENSION_NAME_PATTERN.fullmatch(name):
            errors.append(f"import name is invalid: {name!r}")
        if kind not in VALID_KINDS:
            errors.append(f"import {name!r} has invalid kind: {kind!r}")
        if isinstance(path, str):
            resolved = (root / path).resolve(strict=False)
            try:
                resolved.relative_to(root)
            except ValueError:
                errors.append(f"import {name!r} path escapes the repository")
            if not resolved.exists():
                errors.append(f"import {name!r} path does not exist: {path}")
    return errors


def _validate_extensions(extensions: object) -> list[str]:
    if not isinstance(extensions, list):
        return ["extensions must be an array"]
    errors: list[str] = []
    seen: set[str] = set()
    for extension in extensions:
        if not isinstance(extension, dict):
            errors.append("extension entries must be objects")
            continue
        kind = extension.get("kind")
        name = extension.get("name")
        key = f"{kind}:{name}"
        if kind not in VALID_KINDS:
            errors.append(f"{key} has invalid kind")
        if not isinstance(name, str) or not EXTENSION_NAME_PATTERN.fullmatch(name):
            errors.append(f"{key} has invalid name")
        if key in seen:
            errors.append(f"{key} is duplicated")
        seen.add(key)
        source = extension.get("source", "local")
        if source not in VALID_SOURCES:
            errors.append(f"{key} has invalid source")
        risk_level = extension.get("risk_level")
        if risk_level is not None and risk_level not in VALID_RISK_LEVELS:
            errors.append(f"{key} has invalid risk_level")
        entrypoint = extension.get("entrypoint")
        if kind in {"agent", "tool", "skill"} and not isinstance(entrypoint, str):
            errors.append(f"{key} must define an entrypoint")
    return errors


def _check_import_guardrails(root: Path) -> CheckResult:
    router_path = root / "backend" / "app" / "gateway" / "routers" / "extensions.py"
    text = router_path.read_text(encoding="utf-8")
    required_prefixes = {
        "internal_tools.",
        "internal_agents.",
        "internal_skills/",
        "deerflow.",
    }
    missing_prefixes = sorted(
        prefix for prefix in required_prefixes if prefix not in text
    )
    has_byte_limit = "_DEFAULT_IMPORT_MAX_BYTES = 512 * 1024" in text
    has_count_limit = "_DEFAULT_IMPORT_MAX_EXTENSIONS = 200" in text
    has_safety_validation = (
        "_import_safety_messages" in text
        and "DEERFLOW_EXTENSION_IMPORT_ENTRYPOINT_PREFIXES" in text
    )
    has_schema_policy = (
        "DEERFLOW_EXTENSION_IMPORT_SCHEMA_VERSIONS" in text
        and "_import_manifest_policy_errors" in text
    )
    has_source_allowlist = "DEERFLOW_EXTENSION_IMPORT_ALLOWED_SOURCES" in text
    has_rejected_import_audit = (
        "extension.import.rejected" in text and "record_audit_event" in text
    )
    if not has_byte_limit:
        return CheckResult(
            "import guardrails", False, "default 512 KiB manifest limit is missing"
        )
    if not has_count_limit:
        return CheckResult(
            "import guardrails", False, "default 200 descriptor limit is missing"
        )
    if missing_prefixes:
        return CheckResult(
            "import guardrails",
            False,
            "missing allowed prefixes: " + ", ".join(missing_prefixes),
        )
    if not has_safety_validation:
        return CheckResult(
            "import guardrails", False, "import safety validation helper is missing"
        )
    if not has_schema_policy:
        return CheckResult(
            "import guardrails", False, "schema version policy validation is missing"
        )
    if not has_source_allowlist:
        return CheckResult(
            "import guardrails",
            False,
            "registry source allowlist validation is missing",
        )
    if not has_rejected_import_audit:
        return CheckResult(
            "import guardrails",
            False,
            "rejected registry imports are not audited",
        )
    return CheckResult(
        "import guardrails",
        True,
        "byte/count limits, schema versions, source allowlist, rejected-import audit, and entrypoint prefix validation enabled",
    )


def _check_admin_readiness_endpoint(root: Path) -> CheckResult:
    router = root / "backend" / "app" / "gateway" / "routers" / "readiness.py"
    app = root / "backend" / "app" / "gateway" / "app.py"
    docs = root / "docs" / "enterprise-readiness.md"
    tests = root / "backend" / "tests" / "test_readiness_router.py"
    missing = [
        path.relative_to(root).as_posix()
        for path in (router, app, docs, tests)
        if not path.is_file()
    ]
    if missing:
        return CheckResult(
            "admin readiness endpoint", False, "missing: " + ", ".join(missing)
        )

    router_text = router.read_text(encoding="utf-8")
    app_text = app.read_text(encoding="utf-8")
    docs_text = docs.read_text(encoding="utf-8")
    required_router_phrases = [
        'APIRouter(prefix="/api/readiness"',
        "require_admin_user",
        "model_credentials",
        "registry_policy",
        "artifact_storage",
    ]
    missing_phrases = [
        phrase for phrase in required_router_phrases if phrase not in router_text
    ]
    if "readiness.router" not in app_text:
        missing_phrases.append("gateway router registration")
    if "Admin Readiness Status" not in docs_text:
        missing_phrases.append("Admin Readiness Status docs")
    return CheckResult(
        "admin readiness endpoint",
        not missing_phrases,
        "admin-only readiness endpoint covers auth, credentials, tracing, registry policy, and artifact storage"
        if not missing_phrases
        else "missing: " + ", ".join(missing_phrases),
    )


def _check_runtime_approval_policy(root: Path) -> CheckResult:
    descriptors = root / "backend" / "packages" / "harness" / "deerflow" / "extensions" / "descriptors.py"
    policy = root / "backend" / "packages" / "harness" / "deerflow" / "extensions" / "policy.py"
    readiness = root / "backend" / "app" / "gateway" / "routers" / "readiness.py"
    docs = root / "docs" / "extension-registry-schema.md"
    tests = root / "backend" / "tests" / "test_extension_registry.py"
    missing = [
        path.relative_to(root).as_posix()
        for path in (descriptors, policy, readiness, docs, tests)
        if not path.is_file()
    ]
    if missing:
        return CheckResult(
            "runtime approval policy", False, "missing: " + ", ".join(missing)
        )

    checks = {
        "ExtensionApproval descriptor": "ExtensionApproval" in descriptors.read_text(encoding="utf-8"),
        "high-risk approval env": "DEERFLOW_EXTENSION_REQUIRE_HIGH_RISK_APPROVAL" in policy.read_text(encoding="utf-8"),
        "approval enforcement": "requires descriptor approval" in policy.read_text(encoding="utf-8"),
        "readiness approval status": "require_high_risk_approval" in readiness.read_text(encoding="utf-8"),
        "approval docs": "`approval`" in docs.read_text(encoding="utf-8"),
        "approval tests": "test_materialize_tool_allows_approved_high_risk" in tests.read_text(encoding="utf-8"),
    }
    missing_checks = [name for name, ok in checks.items() if not ok]
    return CheckResult(
        "runtime approval policy",
        not missing_checks,
        "high-risk capabilities require descriptor approval by default"
        if not missing_checks
        else "missing: " + ", ".join(missing_checks),
    )


def _check_generated_registry_gitignored(root: Path) -> CheckResult:
    gitignore = root / ".gitignore"
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    ignored_in_file = "registries/imported_extensions.json" in text
    tracked = _git_file_is_tracked(root, "registries/imported_extensions.json")
    return CheckResult(
        "generated registry isolation",
        ignored_in_file and not tracked,
        "registries/imported_extensions.json is gitignored and untracked"
        if ignored_in_file and not tracked
        else f"gitignored={ignored_in_file}, tracked={tracked}",
    )


def _check_frontend_env_example(root: Path) -> CheckResult:
    env_example = root / "frontend" / ".env.example"
    if not env_example.is_file():
        return CheckResult(
            "frontend env example", False, "frontend/.env.example is missing"
        )
    text = env_example.read_text(encoding="utf-8")
    required = [
        "NEXT_PUBLIC_BACKEND_BASE_URL",
        "NEXT_PUBLIC_LANGGRAPH_BASE_URL",
        "DEER_FLOW_INTERNAL_GATEWAY_BASE_URL",
        "DEER_FLOW_TRUSTED_ORIGINS",
    ]
    missing = [name for name in required if name not in text]
    return CheckResult(
        "frontend env example",
        not missing,
        "split UI/gateway deployment variables documented"
        if not missing
        else "missing: " + ", ".join(missing),
    )


def _check_demo_docs(root: Path) -> CheckResult:
    docs = [
        root / "docs" / "hackathon-demo.md",
        root / "docs" / "extension-registry-schema.md",
        root / "docs" / "split-ui-deployment.md",
    ]
    missing = [path.relative_to(root).as_posix() for path in docs if not path.is_file()]
    if missing:
        return CheckResult("demo docs", False, "missing: " + ", ".join(missing))
    schema = docs[1].read_text(encoding="utf-8")
    split_ui = docs[2].read_text(encoding="utf-8")
    required_phrases = [
        "Extension Registry Schema",
        "Import Guardrails",
        "Minimal External Registry Example",
    ]
    missing_phrases = [phrase for phrase in required_phrases if phrase not in schema]
    split_ui_required = [
        "Split UI Deployment Guide",
        "DEER_FLOW_INTERNAL_GATEWAY_BASE_URL",
        "NEXT_PUBLIC_BACKEND_BASE_URL",
        "GATEWAY_CORS_ORIGINS",
    ]
    missing_split_ui = [
        phrase for phrase in split_ui_required if phrase not in split_ui
    ]
    if missing_split_ui:
        return CheckResult(
            "demo docs", False, "split UI guide missing: " + ", ".join(missing_split_ui)
        )
    return CheckResult(
        "demo docs",
        not missing_phrases,
        "schema, demo guide, and split UI guide present"
        if not missing_phrases
        else "schema missing: " + ", ".join(missing_phrases),
    )


def _check_demo_deploy_bundle(root: Path) -> CheckResult:
    compose = root / "docker" / "docker-compose.hackathon-demo.yaml"
    env_example = root / "docker" / "hackathon-demo.env.example"
    smoke = root / "scripts" / "hackathon_demo_deploy_smoke.py"
    launcher = root / "scripts" / "run_hackathon_demo.py"
    split_ui = root / "docs" / "split-ui-deployment.md"
    gitignore = root / ".gitignore"
    required = [compose, env_example, smoke, launcher, split_ui, gitignore]
    missing = [
        path.relative_to(root).as_posix() for path in required if not path.is_file()
    ]
    if missing:
        return CheckResult(
            "demo deploy bundle", False, "missing: " + ", ".join(missing)
        )

    compose_text = compose.read_text(encoding="utf-8")
    env_text = env_example.read_text(encoding="utf-8")
    docs_text = split_ui.read_text(encoding="utf-8")
    gitignore_text = gitignore.read_text(encoding="utf-8")
    required_compose_phrases = [
        "frontend:",
        "gateway:",
        "DEER_FLOW_INTERNAL_GATEWAY_BASE_URL=http://gateway:8001",
        "DEERFLOW_EXTENSION_MANIFESTS=${DEERFLOW_EXTENSION_MANIFESTS:-registries/demo_extensions.json}",
        "DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS=${DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS:-low,medium}",
        "../internal_tools:/app/internal_tools:ro",
    ]
    required_env_phrases = [
        "HACKATHON_FRONTEND_PORT=3000",
        "HACKATHON_GATEWAY_PORT=8001",
        "OPENAI_API_KEY=",
    ]
    required_docs_phrases = [
        "Hackathon Split Demo Bundle",
        "docker-compose.hackathon-demo.yaml",
        "hackathon_demo_deploy_smoke.py",
        "run_hackathon_demo.py",
    ]
    required_gitignore_phrases = [
        "docker/hackathon-demo.env",
    ]
    missing_compose = [
        phrase for phrase in required_compose_phrases if phrase not in compose_text
    ]
    missing_env = [phrase for phrase in required_env_phrases if phrase not in env_text]
    missing_docs = [
        phrase for phrase in required_docs_phrases if phrase not in docs_text
    ]
    missing_gitignore = [
        phrase for phrase in required_gitignore_phrases if phrase not in gitignore_text
    ]
    missing_all = [*missing_compose, *missing_env, *missing_docs, *missing_gitignore]
    return CheckResult(
        "demo deploy bundle",
        not missing_all,
        "split demo compose, env example, and smoke command are present"
        if not missing_all
        else "missing: " + ", ".join(missing_all[:5]),
    )


def _check_enterprise_runtime_env(root: Path, env_file: Path | None) -> CheckResult:
    path = _resolve_env_file(root, env_file)
    if not path.is_file():
        return CheckResult("enterprise runtime env", False, f"missing env file: {path}")

    values = _read_env_file(path)
    errors: list[str] = []
    if _is_truthy(_effective_value(values, "DEER_FLOW_AUTH_DISABLED")):
        errors.append("DEER_FLOW_AUTH_DISABLED must be false or unset")
    if _is_truthy(_effective_value(values, "GATEWAY_ENABLE_DOCS")):
        errors.append("GATEWAY_ENABLE_DOCS must be false or unset")

    auth_secret = _effective_value(values, "BETTER_AUTH_SECRET")
    if (
        not auth_secret
        or auth_secret == PLACEHOLDER_AUTH_SECRET
        or len(auth_secret) < 32
    ):
        errors.append(
            "BETTER_AUTH_SECRET must be a non-placeholder value at least 32 characters long"
        )

    if not any(_effective_value(values, name) for name in MODEL_CREDENTIAL_ENV_VARS):
        errors.append("at least one model credential env var must be set")

    trusted_origins = _effective_value(values, "DEER_FLOW_TRUSTED_ORIGINS")
    cors_origins = _effective_value(values, "GATEWAY_CORS_ORIGINS")
    for key, value in (
        ("DEER_FLOW_TRUSTED_ORIGINS", trusted_origins),
        ("GATEWAY_CORS_ORIGINS", cors_origins),
    ):
        if not value:
            errors.append(f"{key} must be set")
        elif "*" in _split_csv(value):
            errors.append(f"{key} must not contain wildcard origins")

    risk_levels = {
        item.lower()
        for item in _split_csv(
            _effective_value(values, "DEERFLOW_EXTENSION_ALLOWED_RISK_LEVELS")
        )
    }
    if "high" in risk_levels:
        errors.append("high-risk extensions must not be enabled by default")

    python_allowlist = _split_csv(
        _effective_value(values, "DEERFLOW_PYTHON_FUNCTION_ALLOWLIST")
    )
    if "*" in python_allowlist:
        errors.append("DEERFLOW_PYTHON_FUNCTION_ALLOWLIST must not contain wildcards")

    return CheckResult(
        "enterprise runtime env",
        not errors,
        "auth enabled, docs disabled, credentials present, CORS restricted, high-risk defaults disabled"
        if not errors
        else "; ".join(errors[:5]),
    )


def _resolve_env_file(root: Path, env_file: Path | None) -> Path:
    if env_file is None:
        return root / "docker" / "hackathon-demo.env"
    if env_file.is_absolute():
        return env_file
    return root / env_file


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _effective_value(values: dict[str, str], key: str) -> str:
    return values.get(key) or os.environ.get(key, "")


def _split_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in TRUTHY_VALUES


def _git_file_is_tracked(root: Path, path: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return completed.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run production readiness checks for the hackathon app."
    )
    parser.add_argument("--project-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--profile",
        choices=("demo", "enterprise"),
        default="demo",
        help="Use 'demo' for smoke-friendly checks or 'enterprise' for production-like runtime env checks.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Runtime env file to validate when --profile enterprise is used.",
    )
    args = parser.parse_args(argv)

    results = run_readiness_checks(
        args.project_root, profile=args.profile, env_file=args.env_file
    )

    print("Production readiness report")
    print(f"Project root: {args.project_root.resolve(strict=False)}")
    print(f"Profile: {args.profile}")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"[{status}] {result.name}: {result.detail}")
    failures = [result for result in results if not result.ok]
    if failures:
        print(f"Readiness failed: {len(failures)} check(s) need attention.")
        return 1
    print("Readiness passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
