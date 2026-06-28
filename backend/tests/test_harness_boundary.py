"""Boundary check: harness layer must not import from app layer.

The deerflow-harness package (packages/harness/deerflow/) is a standalone,
publishable agent framework. It must never depend on the app layer (app/).

This test scans all Python files in the harness package and fails if any
``from app.`` or ``import app.`` statement is found.
"""

import ast
import tomllib
from pathlib import Path

HARNESS_ROOT = Path(__file__).parent.parent / "packages" / "harness" / "deerflow"
HARNESS_PACKAGE_ROOT = HARNESS_ROOT.parent

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


def test_harness_public_api_exports_stable_sdk_surface():
    import deerflow

    expected = {
        "DeerFlowClient",
        "ExtensionCatalog",
        "ExtensionDescriptor",
        "ExtensionKind",
        "ExtensionManifest",
        "generate_pdf_report",
        "load_extension_catalog",
        "validate_extension_registry",
    }

    assert expected.issubset(set(deerflow.__all__))
    assert deerflow.ExtensionKind.TOOL.value == "tool"
