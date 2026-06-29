export type ArtifactFileKind = "html" | "pdf" | "csv" | "markdown" | "other";

export type ArtifactCatalogSummary = {
  total: number;
  byKind: Record<ArtifactFileKind, number>;
};

const ARTIFACT_KINDS: ArtifactFileKind[] = [
  "html",
  "pdf",
  "csv",
  "markdown",
  "other",
];

export function summarizeArtifactFiles(
  files: string[],
): ArtifactCatalogSummary {
  const byKind = Object.fromEntries(
    ARTIFACT_KINDS.map((kind) => [kind, 0]),
  ) as Record<ArtifactFileKind, number>;

  for (const file of files) {
    byKind[getArtifactFileKind(file)] += 1;
  }

  return {
    total: files.length,
    byKind,
  };
}

export function getArtifactFileKind(filepath: string): ArtifactFileKind {
  const normalized = filepath.toLowerCase().split("?")[0] ?? filepath;
  if (normalized.endsWith(".html") || normalized.endsWith(".htm")) {
    return "html";
  }
  if (normalized.endsWith(".pdf")) {
    return "pdf";
  }
  if (normalized.endsWith(".csv")) {
    return "csv";
  }
  if (normalized.endsWith(".md") || normalized.endsWith(".markdown")) {
    return "markdown";
  }
  return "other";
}

export function formatArtifactSummary(summary: ArtifactCatalogSummary): string {
  const parts = [
    ["HTML", summary.byKind.html],
    ["PDF", summary.byKind.pdf],
    ["CSV", summary.byKind.csv],
    ["Markdown", summary.byKind.markdown],
    ["Other", summary.byKind.other],
  ].filter(([, count]) => Number(count) > 0);

  if (parts.length === 0) {
    return "No generated artifacts";
  }

  return parts.map(([label, count]) => `${count} ${label}`).join(" · ");
}
