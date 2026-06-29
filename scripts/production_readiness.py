from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

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


def run_readiness_checks(project_root: Path = REPO_ROOT) -> list[CheckResult]:
    root = project_root.resolve(strict=False)
    results: list[CheckResult] = []
    results.append(_check_required_paths(root))
    results.append(_check_demo_registry(root))
    results.append(_check_import_guardrails())
    results.append(_check_generated_registry_gitignored(root))
    results.append(_check_frontend_env_example(root))
    results.append(_check_demo_docs(root))
    results.append(_check_demo_deploy_bundle(root))
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
    missing = [path.relative_to(root).as_posix() for path in required if not path.exists()]
    return CheckResult(
        "required paths",
        not missing,
        "all expected harness/UI/internal registry paths exist" if not missing else "missing: " + ", ".join(missing),
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

    enabled_agents = {extension["name"] for extension in extensions if extension.get("kind") == "agent" and extension.get("enabled") is True}
    enabled_tools = {extension["name"] for extension in extensions if extension.get("kind") == "tool" and extension.get("enabled") is True}
    missing_tools = sorted(REQUIRED_DEMO_TOOLS - enabled_tools)
    if "reporting-agent" not in enabled_agents:
        return CheckResult("demo registry", False, "reporting-agent is not enabled")
    if missing_tools:
        return CheckResult("demo registry", False, "missing enabled tools: " + ", ".join(missing_tools))
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


def _check_import_guardrails() -> CheckResult:
    router_path = REPO_ROOT / "backend" / "app" / "gateway" / "routers" / "extensions.py"
    text = router_path.read_text(encoding="utf-8")
    required_prefixes = {"internal_tools.", "internal_agents.", "internal_skills/", "deerflow."}
    missing_prefixes = sorted(prefix for prefix in required_prefixes if prefix not in text)
    has_byte_limit = "_DEFAULT_IMPORT_MAX_BYTES = 512 * 1024" in text
    has_count_limit = "_DEFAULT_IMPORT_MAX_EXTENSIONS = 200" in text
    has_safety_validation = "_import_safety_messages" in text and "DEERFLOW_EXTENSION_IMPORT_ENTRYPOINT_PREFIXES" in text
    if not has_byte_limit:
        return CheckResult("import guardrails", False, "default 512 KiB manifest limit is missing")
    if not has_count_limit:
        return CheckResult("import guardrails", False, "default 200 descriptor limit is missing")
    if missing_prefixes:
        return CheckResult("import guardrails", False, "missing allowed prefixes: " + ", ".join(missing_prefixes))
    if not has_safety_validation:
        return CheckResult("import guardrails", False, "import safety validation helper is missing")
    return CheckResult(
        "import guardrails",
        True,
        "512 KiB byte limit, 200 descriptor limit, entrypoint prefix validation enabled",
    )


def _check_generated_registry_gitignored(root: Path) -> CheckResult:
    gitignore = root / ".gitignore"
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    ignored_in_file = "registries/imported_extensions.json" in text
    tracked = _git_file_is_tracked(root, "registries/imported_extensions.json")
    return CheckResult(
        "generated registry isolation",
        ignored_in_file and not tracked,
        "registries/imported_extensions.json is gitignored and untracked" if ignored_in_file and not tracked else f"gitignored={ignored_in_file}, tracked={tracked}",
    )


def _check_frontend_env_example(root: Path) -> CheckResult:
    env_example = root / "frontend" / ".env.example"
    if not env_example.is_file():
        return CheckResult("frontend env example", False, "frontend/.env.example is missing")
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
        "split UI/gateway deployment variables documented" if not missing else "missing: " + ", ".join(missing),
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
    missing_split_ui = [phrase for phrase in split_ui_required if phrase not in split_ui]
    if missing_split_ui:
        return CheckResult("demo docs", False, "split UI guide missing: " + ", ".join(missing_split_ui))
    return CheckResult(
        "demo docs",
        not missing_phrases,
        "schema, demo guide, and split UI guide present" if not missing_phrases else "schema missing: " + ", ".join(missing_phrases),
    )


def _check_demo_deploy_bundle(root: Path) -> CheckResult:
    compose = root / "docker" / "docker-compose.hackathon-demo.yaml"
    env_example = root / "docker" / "hackathon-demo.env.example"
    smoke = root / "scripts" / "hackathon_demo_deploy_smoke.py"
    split_ui = root / "docs" / "split-ui-deployment.md"
    gitignore = root / ".gitignore"
    required = [compose, env_example, smoke, split_ui, gitignore]
    missing = [path.relative_to(root).as_posix() for path in required if not path.is_file()]
    if missing:
        return CheckResult("demo deploy bundle", False, "missing: " + ", ".join(missing))

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
    ]
    required_gitignore_phrases = [
        "docker/hackathon-demo.env",
    ]
    missing_compose = [phrase for phrase in required_compose_phrases if phrase not in compose_text]
    missing_env = [phrase for phrase in required_env_phrases if phrase not in env_text]
    missing_docs = [phrase for phrase in required_docs_phrases if phrase not in docs_text]
    missing_gitignore = [phrase for phrase in required_gitignore_phrases if phrase not in gitignore_text]
    missing_all = [*missing_compose, *missing_env, *missing_docs, *missing_gitignore]
    return CheckResult(
        "demo deploy bundle",
        not missing_all,
        "split demo compose, env example, and smoke command are present"
        if not missing_all
        else "missing: " + ", ".join(missing_all[:5]),
    )


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
    parser = argparse.ArgumentParser(description="Run production readiness checks for the hackathon app.")
    parser.add_argument("--project-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)

    results = run_readiness_checks(args.project_root)

    print("Production readiness report")
    print(f"Project root: {args.project_root.resolve(strict=False)}")
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
