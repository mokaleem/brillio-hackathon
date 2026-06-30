"""Boundary check: harness layer must not import from app layer.

The deerflow-harness package (packages/harness/deerflow/) is a standalone,
publishable agent framework. It must never depend on the app layer (app/).

This test scans all Python files in the harness package and fails if any
``from app.`` or ``import app.`` statement is found.
"""

import ast
import json
import os
import subprocess
import tomllib
import venv
from pathlib import Path

HARNESS_ROOT = Path(__file__).parent.parent / "packages" / "harness" / "deerflow"
HARNESS_PACKAGE_ROOT = HARNESS_ROOT.parent
BACKEND_ROOT = HARNESS_PACKAGE_ROOT.parent.parent
REPO_ROOT = BACKEND_ROOT.parent
SDK_CONSUMER = REPO_ROOT / "examples" / "harness-sdk-consumer" / "consumer.py"

BANNED_PREFIXES = ("app.",)


def _collect_imports(filepath: Path) -> list[tuple[int, str]]:
    """Return (line_number, module_path) for every import in *filepath*."""
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    results: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                results.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                results.append((node.lineno, node.module))
    return results


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert completed.returncode == 0, f"{' '.join(command)} failed:\n{completed.stdout}"
    return completed


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def test_harness_does_not_import_app():
    violations: list[str] = []

    for py_file in sorted(HARNESS_ROOT.rglob("*.py")):
        for lineno, module in _collect_imports(py_file):
            if any(module == prefix.rstrip(".") or module.startswith(prefix) for prefix in BANNED_PREFIXES):
                rel = py_file.relative_to(HARNESS_ROOT.parent.parent.parent)
                violations.append(f"  {rel}:{lineno}  imports {module}")

    assert not violations, "Harness layer must not import from app layer:\n" + "\n".join(violations)


def test_harness_package_readme_exists():
    pyproject = tomllib.loads((HARNESS_PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    readme = pyproject["project"]["readme"]

    assert (HARNESS_PACKAGE_ROOT / readme).is_file()


def test_external_sdk_consumer_example_exists():
    assert SDK_CONSUMER.is_file()
    readme = SDK_CONSUMER.with_name("README.md")
    assert "deerflow-harness" in readme.read_text(encoding="utf-8")


def test_harness_public_api_exports_stable_sdk_surface():
    import deerflow

    expected = {
        "DeerFlowClient",
        "ExtensionCatalog",
        "ExtensionDescriptor",
        "ExtensionKind",
        "ExtensionManifest",
        "generate_csv_file",
        "generate_html_report",
        "generate_pdf_report",
        "load_extension_catalog",
        "validate_extension_registry",
    }

    assert expected.issubset(set(deerflow.__all__))
    assert deerflow.ExtensionKind.TOOL.value == "tool"


def test_harness_wheel_installs_and_imports_public_sdk(tmp_path: Path):
    dist_dir = tmp_path / "dist"
    _run(["uv", "build", "packages/harness", "--wheel", "--out-dir", str(dist_dir)], cwd=BACKEND_ROOT)

    wheels = sorted(dist_dir.glob("deerflow_harness-*.whl"))
    assert len(wheels) == 1

    venv_dir = tmp_path / "sdk-venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(venv_dir)
    python = _venv_python(venv_dir)

    _run(["uv", "pip", "install", "--python", str(python), str(wheels[0])], cwd=tmp_path)

    smoke = """
from pathlib import Path
import sys

import deerflow
from deerflow import (
    DeerFlowClient,
    ExtensionKind,
    generate_csv_file,
    generate_html_report,
    generate_pdf_report,
    load_extension_catalog,
    validate_extension_registry,
)

installed_from = Path(deerflow.__file__).resolve()
venv_root = Path(sys.prefix).resolve()

assert str(installed_from).startswith(str(venv_root)), installed_from
assert deerflow.__version__ == "2.1.0"
assert ExtensionKind.TOOL.value == "tool"
assert callable(DeerFlowClient)
assert callable(load_extension_catalog)
assert callable(validate_extension_registry)
assert callable(generate_csv_file)
assert callable(generate_html_report)
assert callable(generate_pdf_report)
"""

    env = {**os.environ, "PYTHONPATH": ""}
    _run([str(python), "-c", smoke], cwd=tmp_path, env=env)

    external_manifest = tmp_path / "external-registry.json"
    external_manifest.write_text(
        """
        {
          "version": 1,
          "extensions": [
            {
              "kind": "tool",
              "name": "sdk-report",
              "enabled": true,
              "source": "registry",
              "entrypoint": "company_tools.sdk:report",
              "risk_level": "low"
            },
            {
              "kind": "skill",
              "name": "sdk-summary",
              "enabled": true,
              "source": "registry",
              "entrypoint": "company_skills/sdk-summary",
              "risk_level": "low"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    output_dir = tmp_path / "consumer-output"
    completed = _run(
        [
            str(python),
            str(SDK_CONSUMER),
            "--repo-root",
            str(tmp_path),
            "--manifest",
            str(external_manifest),
            "--output-dir",
            str(output_dir),
        ],
        cwd=tmp_path,
        env=env,
    )
    payload = json.loads(completed.stdout)
    installed_from = Path(payload["installed_from"]).resolve()
    assert str(installed_from).startswith(str(venv_dir.resolve()))
    assert payload["enabled"] == ["tool:sdk-report", "skill:sdk-summary"]
    assert [Path(path).suffix for path in payload["artifacts"]] == [".html", ".csv", ".pdf"]
    assert all(Path(path).is_file() for path in payload["artifacts"])
