from __future__ import annotations

import argparse
import json
from pathlib import Path

import deerflow
from deerflow import (
    ExtensionKind,
    generate_csv_file,
    generate_html_report,
    generate_pdf_report,
    load_extension_catalog,
    validate_extension_registry,
)


def run_consumer(*, repo_root: Path, manifest: Path, output_dir: Path) -> dict[str, object]:
    repo_root = repo_root.resolve(strict=False)
    manifest = manifest.resolve(strict=False)
    output_dir = output_dir.resolve(strict=False)
    output_dir.mkdir(parents=True, exist_ok=True)

    health = validate_extension_registry([manifest], repo_root=repo_root)
    if not health.valid:
        raise RuntimeError("Registry validation failed: " + "; ".join(health.errors))

    catalog = load_extension_catalog([manifest], repo_root=repo_root)
    enabled = list(catalog.enabled())
    rows = [
        {
            "kind": extension.kind.value,
            "name": extension.name,
            "risk": extension.risk_level or "",
        }
        for extension in enabled
    ]
    enabled_names = [f"{extension.kind.value}:{extension.name}" for extension in enabled]

    html_path = generate_html_report(
        title="Harness SDK Consumer",
        sections=[
            (
                "Enabled Capabilities",
                ", ".join(enabled_names) if enabled_names else "No enabled capabilities",
            )
        ],
        output_path=output_dir / "capabilities.html",
    )
    csv_path = generate_csv_file(
        rows=rows,
        fieldnames=["kind", "name", "risk"],
        output_path=output_dir / "capabilities.csv",
    )
    pdf_path = generate_pdf_report(
        title="Harness SDK Consumer",
        lines=[
            f"Loaded {len(enabled)} enabled capabilities.",
            f"Tools: {len(list(catalog.enabled(kind=ExtensionKind.TOOL)))}",
        ],
        output_path=output_dir / "capabilities.pdf",
    )

    return {
        "deerflow_version": deerflow.__version__,
        "installed_from": str(Path(deerflow.__file__).resolve()),
        "enabled": enabled_names,
        "artifacts": [str(html_path), str(csv_path), str(pdf_path)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an external deerflow-harness SDK consumer smoke test.")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    print(json.dumps(run_consumer(repo_root=args.repo_root, manifest=args.manifest, output_dir=args.output_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
