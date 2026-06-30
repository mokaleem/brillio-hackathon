from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from deerflow.tools.tools import get_available_tools

REPO_ROOT = Path(__file__).resolve().parents[2]


def _reporting_tools():
    root_text = str(REPO_ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    module = importlib.import_module("internal_tools.reporting")
    return module.csv_export, module.html_report, module.pdf_report


def test_html_report_tool_writes_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DEER_FLOW_HOME", str(tmp_path))
    _csv_export, html_report, _pdf_report = _reporting_tools()

    output = html_report.invoke(
        {
            "title": "Demo",
            "sections_json": json.dumps([{"title": "Summary", "body": "Ready for judges"}]),
        }
    )

    assert "html-report-" in output
    generated = next((tmp_path / "artifacts").glob("html-report-*.html"))
    assert "Ready for judges" in generated.read_text(encoding="utf-8")


def test_csv_export_tool_writes_csv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DEER_FLOW_HOME", str(tmp_path))
    csv_export, _html_report, _pdf_report = _reporting_tools()

    output = csv_export.invoke(
        {
            "rows_json": json.dumps(
                [
                    {"name": "Activation", "value": 42},
                    {"name": "Retention", "value": 87},
                ]
            )
        }
    )

    assert "csv-export-" in output
    generated = next((tmp_path / "artifacts").glob("csv-export-*.csv"))
    assert generated.read_text(encoding="utf-8").splitlines()[0] == "name,value"


def test_pdf_report_tool_writes_pdf(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DEER_FLOW_HOME", str(tmp_path))
    _csv_export, _html_report, pdf_report = _reporting_tools()

    output = pdf_report.invoke(
        {
            "title": "Demo PDF",
            "sections_json": json.dumps([{"title": "Summary", "body": "Ready for review"}]),
        }
    )

    assert "pdf-report-" in output
    generated = next((tmp_path / "artifacts").glob("pdf-report-*.pdf"))
    data = generated.read_bytes()
    assert data.startswith(b"%PDF-1.4")
    assert b"Ready for review" in data


@patch("deerflow.tools.tools.is_host_bash_allowed", return_value=True)
def test_demo_registry_reporting_tools_load_into_orchestration(mock_bash, monkeypatch) -> None:
    monkeypatch.setenv("DEER_FLOW_PROJECT_ROOT", str(REPO_ROOT))
    monkeypatch.setenv("DEERFLOW_EXTENSION_MANIFESTS", "registries/demo_extensions.json")

    config = MagicMock()
    config.tools = []
    config.models = []
    config.tool_search.enabled = False
    config.skill_evolution.enabled = False
    config.sandbox = MagicMock()
    config.acp_agents = {}

    with patch("deerflow.tools.tools.BUILTIN_TOOLS", []):
        tools = get_available_tools(groups=["reporting"], include_mcp=False, app_config=config)

    assert [tool.name for tool in tools] == ["html_report", "csv_export", "pdf_report"]
