from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = REPO_ROOT / "backend" / "packages" / "harness"

for path in (str(REPO_ROOT), str(HARNESS_PATH)):
    if path not in sys.path:
        sys.path.insert(0, path)

from deerflow.internal_registry import (  # noqa: E402
    ExtensionKind,
    load_extension_catalog,
    materialize_tool,
    validate_extension_registry,
)

MANIFEST_PATH = Path("registries/demo_extensions.json")
PYTHON_ENTRYPOINT = "internal_tools.python_examples:summarize_metrics"


@dataclass(frozen=True)
class DemoSmokeResult:
    manifest: Path
    artifact_home: Path
    tool_names: tuple[str, ...]
    generated_artifacts: tuple[Path, ...]
    python_result: dict[str, object]


def run_demo_smoke(
    project_root: Path = REPO_ROOT,
    *,
    artifact_home: Path | None = None,
) -> DemoSmokeResult:
    root = project_root.resolve(strict=False)
    manifest = (root / MANIFEST_PATH).resolve(strict=False)
    home = (artifact_home or root / ".deer-flow" / "demo-smoke").resolve(strict=False)
    home.mkdir(parents=True, exist_ok=True)

    with _temporary_env(
        {
            "DEER_FLOW_PROJECT_ROOT": str(root),
            "DEER_FLOW_HOME": str(home),
            "DEERFLOW_EXTENSION_MANIFESTS": str(MANIFEST_PATH),
            "DEERFLOW_PYTHON_FUNCTION_ALLOWLIST": PYTHON_ENTRYPOINT,
        }
    ):
        health = validate_extension_registry([MANIFEST_PATH], repo_root=root)
        if not health.valid:
            raise RuntimeError("Demo extension registry is invalid:\n" + "\n".join(health.errors))

        catalog = load_extension_catalog([manifest], repo_root=root)
        tools = {tool.name: tool for tool in (materialize_tool(extension) for extension in catalog.enabled(kind=ExtensionKind.TOOL))}

        required_tools = {"html_report", "csv_export", "pdf_report", "python_function"}
        missing_tools = sorted(required_tools - tools.keys())
        if missing_tools:
            raise RuntimeError(f"Demo registry is missing required tools: {', '.join(missing_tools)}")

        sections_json = json.dumps(
            [
                {
                    "title": "Dynamic Registry",
                    "body": "Agents, MCP servers, tools, and skills load from manifests outside the harness package.",
                },
                {
                    "title": "Artifact Harness",
                    "body": "The same registry tools can generate HTML, CSV, and PDF outputs without an LLM call.",
                },
            ]
        )
        rows_json = json.dumps(
            [
                {"capability": "agents", "status": "dynamic", "score": 95},
                {"capability": "tools", "status": "registry-loaded", "score": 98},
                {"capability": "skills", "status": "discoverable", "score": 92},
            ]
        )
        kwargs_json = json.dumps({"rows": [{"value": 10}, {"value": 20}, {"value": 30}]})

        tool_outputs = [
            str(tools["html_report"].invoke({"title": "Hackathon Demo Smoke", "sections_json": sections_json})),
            str(tools["csv_export"].invoke({"rows_json": rows_json})),
            str(tools["pdf_report"].invoke({"title": "Hackathon Demo Smoke", "sections_json": sections_json})),
        ]
        python_output = str(
            tools["python_function"].invoke(
                {
                    "entrypoint": PYTHON_ENTRYPOINT,
                    "kwargs_json": kwargs_json,
                }
            )
        )

    generated_artifacts = tuple(_artifact_path_from_output(output) for output in tool_outputs)
    missing_artifacts = [path for path in generated_artifacts if not path.is_file()]
    if missing_artifacts:
        raise RuntimeError("Expected demo artifacts were not generated: " + ", ".join(str(path) for path in missing_artifacts))

    python_result = json.loads(python_output)
    return DemoSmokeResult(
        manifest=manifest,
        artifact_home=home,
        tool_names=tuple(sorted(tools)),
        generated_artifacts=generated_artifacts,
        python_result=python_result,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the hackathon demo smoke check without calling an LLM.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root containing registries/demo_extensions.json.",
    )
    parser.add_argument(
        "--artifact-home",
        type=Path,
        default=None,
        help="Writable DeerFlow home for generated demo artifacts. Defaults to .deer-flow/demo-smoke.",
    )
    args = parser.parse_args(argv)

    result = run_demo_smoke(args.project_root, artifact_home=args.artifact_home)
    print("Demo smoke passed")
    print(f"Registry: {result.manifest}")
    print(f"Artifact home: {result.artifact_home}")
    print(f"Loaded tools: {', '.join(result.tool_names)}")
    print("Generated artifacts:")
    for artifact in result.generated_artifacts:
        print(f"  - {artifact}")
    print(f"Python function result: {json.dumps(result.python_result, sort_keys=True)}")
    return 0


@contextmanager
def _temporary_env(updates: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _artifact_path_from_output(output: str) -> Path:
    match = re.search(r":\s*(.+)$", output.strip())
    if not match:
        raise RuntimeError(f"Could not parse artifact path from tool output: {output}")
    return Path(match.group(1)).resolve(strict=False)


if __name__ == "__main__":
    raise SystemExit(main())
