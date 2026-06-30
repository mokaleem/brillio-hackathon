import { describe, expect, test } from "@rstest/core";

import {
  formatArtifactSummary,
  getArtifactFileKind,
  summarizeArtifactFiles,
} from "@/core/artifacts/catalog";

describe("artifact catalog helpers", () => {
  test("classifies common generated report artifacts", () => {
    expect(getArtifactFileKind("/mnt/user-data/outputs/report.html")).toBe(
      "html",
    );
    expect(getArtifactFileKind("/mnt/user-data/outputs/export.csv")).toBe(
      "csv",
    );
    expect(getArtifactFileKind("/mnt/user-data/outputs/summary.pdf")).toBe(
      "pdf",
    );
    expect(getArtifactFileKind("/mnt/user-data/outputs/notes.md")).toBe(
      "markdown",
    );
    expect(getArtifactFileKind("/mnt/user-data/outputs/chart.png")).toBe(
      "other",
    );
  });

  test("summarizes artifact counts by file kind", () => {
    const summary = summarizeArtifactFiles([
      "/mnt/user-data/outputs/report.html",
      "/mnt/user-data/outputs/export.csv",
      "/mnt/user-data/outputs/summary.pdf",
      "/mnt/user-data/outputs/readme.md",
      "/mnt/user-data/outputs/data.json",
    ]);

    expect(summary).toEqual({
      total: 5,
      byKind: {
        html: 1,
        pdf: 1,
        csv: 1,
        markdown: 1,
        other: 1,
      },
    });
    expect(formatArtifactSummary(summary)).toBe(
      "1 HTML · 1 PDF · 1 CSV · 1 Markdown · 1 Other",
    );
  });
});
