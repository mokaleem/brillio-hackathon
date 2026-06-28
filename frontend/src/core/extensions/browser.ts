import type { ExtensionDescriptor, ExtensionKind } from "./types";

export type ExtensionStatusFilter = "all" | "enabled" | "disabled";

export type ExtensionKindFilter = ExtensionKind | "all";

export type ExtensionBrowserFilters = {
  kind: ExtensionKindFilter;
  status: ExtensionStatusFilter;
  query: string;
};

export type ExtensionSummary = {
  total: number;
  enabled: number;
  disabled: number;
  byKind: Record<ExtensionKind, number>;
};

const EXTENSION_KINDS: ExtensionKind[] = ["agent", "mcp", "tool", "skill"];

export function summarizeExtensions(
  extensions: ExtensionDescriptor[],
): ExtensionSummary {
  const byKind = Object.fromEntries(
    EXTENSION_KINDS.map((kind) => [kind, 0]),
  ) as Record<ExtensionKind, number>;

  let enabled = 0;
  for (const extension of extensions) {
    byKind[extension.kind] += 1;
    if (extension.enabled) {
      enabled += 1;
    }
  }

  return {
    total: extensions.length,
    enabled,
    disabled: extensions.length - enabled,
    byKind,
  };
}

export function filterExtensions(
  extensions: ExtensionDescriptor[],
  filters: ExtensionBrowserFilters,
): ExtensionDescriptor[] {
  const query = filters.query.trim().toLowerCase();

  return extensions.filter((extension) => {
    if (filters.kind !== "all" && extension.kind !== filters.kind) {
      return false;
    }
    if (filters.status === "enabled" && !extension.enabled) {
      return false;
    }
    if (filters.status === "disabled" && extension.enabled) {
      return false;
    }
    if (!query) {
      return true;
    }

    const searchable = [
      extension.name,
      extension.display_name,
      extension.description,
      extension.source,
      extension.entrypoint,
      extension.category,
      extension.owner,
      extension.risk_level,
      ...extension.tags,
      ...extension.requires,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return searchable.includes(query);
  });
}

export function applyExtensionEnabledUpdate(
  extensions: ExtensionDescriptor[],
  updated: ExtensionDescriptor,
): ExtensionDescriptor[] {
  return extensions.map((extension) =>
    extension.kind === updated.kind && extension.name === updated.name
      ? updated
      : extension,
  );
}

export function formatExtensionKind(kind: ExtensionKind): string {
  if (kind === "mcp") {
    return "MCP";
  }
  return kind.charAt(0).toUpperCase() + kind.slice(1);
}
