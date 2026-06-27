from pathlib import Path

from deerflow.artifacts import generate_csv_file, generate_html_report, generate_pdf_report


def test_generate_html_report_escapes_content(tmp_path: Path) -> None:
    output = generate_html_report(
        title="Quarterly <Plan>",
        sections=[("Summary", "Revenue > forecast & costs < target")],
        output_path=tmp_path / "report.html",
    )

    content = output.read_text(encoding="utf-8")
    assert output.name == "report.html"
    assert "<title>Quarterly &lt;Plan&gt;</title>" in content
    assert "Revenue &gt; forecast &amp; costs &lt; target" in content


def test_generate_csv_file_writes_headers_and_rows(tmp_path: Path) -> None:
    output = generate_csv_file(
        rows=[
            {"name": "alpha", "score": 10},
            {"name": "beta", "score": 20},
        ],
        output_path=tmp_path / "scores.csv",
    )

    assert output.read_text(encoding="utf-8").splitlines() == ["name,score", "alpha,10", "beta,20"]


def test_generate_pdf_report_writes_minimal_pdf(tmp_path: Path) -> None:
    output = generate_pdf_report(
        title="Promotion Readiness",
        lines=["Architecture is modular.", "Registry loading is configurable."],
        output_path=tmp_path / "report.pdf",
    )

    data = output.read_bytes()
    assert data.startswith(b"%PDF-1.4")
    assert b"Promotion Readiness" in data
    assert data.rstrip().endswith(b"%%EOF")
