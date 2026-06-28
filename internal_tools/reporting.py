from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.tools import tool

from deerflow.artifacts import generate_csv_file, generate_html_report, generate_pdf_report
from deerflow.config.runtime_paths import runtime_home


@tool("html_report")
def html_report(title: str, sections_json: str) -> str:
    """Generate a self-contained HTML report from JSON sections."""
    sections = _parse_sections(sections_json)
    output_path = _artifact_path(f"html-report-{uuid4().hex[:8]}.html")
    generated = generate_html_report(title=title, sections=sections, output_path=output_path)
    return f"HTML report generated: {generated}"


@tool("csv_export")
def csv_export(rows_json: str) -> str:
    """Generate a CSV artifact from a JSON array of objects."""
    rows = _parse_rows(rows_json)
    output_path = _artifact_path(f"csv-export-{uuid4().hex[:8]}.csv")
    generated = generate_csv_file(rows=rows, output_path=output_path)
    return f"CSV file generated: {generated}"


@tool("pdf_report")
def pdf_report(title: str, sections_json: str) -> str:
    """Generate a PDF report from JSON sections."""
    sections = _parse_sections(sections_json)
    lines = _sections_to_pdf_lines(sections)
    output_path = _artifact_path(f"pdf-report-{uuid4().hex[:8]}.pdf")
    generated = generate_pdf_report(title=title, lines=lines, output_path=output_path)
    return f"PDF report generated: {generated}"


def _artifact_path(filename: str) -> Path:
    return runtime_home() / "artifacts" / filename


def _parse_sections(payload: str) -> list[tuple[str, str]]:
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError("sections_json must be a JSON array.")
    sections: list[tuple[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Each section must be an object with title and body.")
        sections.append((str(item.get("title", "Section")), str(item.get("body", ""))))
    return sections


def _parse_rows(payload: str) -> list[dict[str, Any]]:
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError("rows_json must be a JSON array.")
    rows: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Each CSV row must be a JSON object.")
        rows.append(dict(item))
    return rows


def _sections_to_pdf_lines(sections: list[tuple[str, str]]) -> list[str]:
    lines: list[str] = []
    for title, body in sections:
        lines.append(title)
        lines.extend(line for line in body.splitlines() if line.strip())
        lines.append("")
    return lines
