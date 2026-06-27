from __future__ import annotations

import csv
import html
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


def generate_html_report(*, title: str, sections: Sequence[tuple[str, str]], output_path: Path | str) -> Path:
    path = _prepare_output_path(output_path)
    escaped_title = html.escape(title)
    section_markup = "\n".join(
        f"<section><h2>{html.escape(section_title)}</h2><p>{html.escape(body)}</p></section>" for section_title, body in sections
    )
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escaped_title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.5; }}
    main {{ max-width: 840px; }}
    section {{ border-top: 1px solid #ddd; padding: 16px 0; }}
  </style>
</head>
<body>
  <main>
    <h1>{escaped_title}</h1>
    {section_markup}
  </main>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")
    return path


def generate_csv_file(*, rows: Sequence[Mapping[str, Any]], output_path: Path | str, fieldnames: Sequence[str] | None = None) -> Path:
    path = _prepare_output_path(output_path)
    resolved_fieldnames = list(fieldnames or _fieldnames_from_rows(rows))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def generate_pdf_report(*, title: str, lines: Sequence[str], output_path: Path | str) -> Path:
    path = _prepare_output_path(output_path)
    content_lines = [title, "", *lines]
    text_commands = ["BT", "/F1 18 Tf", "72 740 Td", f"({_escape_pdf_text(content_lines[0])}) Tj", "/F1 12 Tf"]
    for line in content_lines[1:]:
        text_commands.append("0 -20 Td")
        text_commands.append(f"({_escape_pdf_text(line)}) Tj")
    text_commands.append("ET")
    stream = "\n".join(text_commands).encode("utf-8")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    path.write_bytes(_build_pdf(objects))
    return path


def _fieldnames_from_rows(rows: Sequence[Mapping[str, Any]]) -> Iterable[str]:
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                yield key


def _prepare_output_path(output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf(objects: Sequence[bytes]) -> bytes:
    chunks = [b"%PDF-1.4\n"]
    offsets: list[int] = []
    cursor = len(chunks[0])
    for index, body in enumerate(objects, start=1):
        offsets.append(cursor)
        chunk = f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
        chunks.append(chunk)
        cursor += len(chunk)

    xref_offset = cursor
    xref_rows = [b"xref\n", f"0 {len(objects) + 1}\n".encode("ascii"), b"0000000000 65535 f \n"]
    xref_rows.extend(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets)
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    return b"".join([*chunks, *xref_rows, trailer])
