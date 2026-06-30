from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_SMOKE_SCRIPT_PATH = REPO_ROOT / "scripts" / "demo_smoke.py"


spec = importlib.util.spec_from_file_location("deerflow_demo_smoke", DEMO_SMOKE_SCRIPT_PATH)
assert spec is not None
assert spec.loader is not None
demo_smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = demo_smoke
spec.loader.exec_module(demo_smoke)


def test_demo_smoke_loads_registry_tools_and_generates_artifacts(tmp_path: Path) -> None:
    result = demo_smoke.run_demo_smoke(REPO_ROOT, artifact_home=tmp_path / "deer-home")

    assert {"html_report", "csv_export", "pdf_report", "python_function"}.issubset(result.tool_names)
    assert [artifact.suffix for artifact in result.generated_artifacts] == [".html", ".csv", ".pdf"]
    assert all(artifact.is_file() for artifact in result.generated_artifacts)
    assert result.python_result == {"count": 3, "total": 60.0, "average": 20.0}
