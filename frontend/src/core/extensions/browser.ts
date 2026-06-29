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

export function extensionDisplayName(extension: ExtensionDescriptor): string {
  return extension.display_name ?? extension.name;
}

export function buildExtensionPrompt(extension: ExtensionDescriptor): string {
  const promptTemplate = metadataString(extension.metadata, "prompt_template");
  if (promptTemplate) {
    return renderExtensionPromptTemplate(promptTemplate, extension);
  }

  const examplePrompt = metadataStringList(
    extension.metadata,
    "example_prompts",
  )[0];
  if (examplePrompt) {
    return examplePrompt;
  }

  const label = extensionDisplayName(extension);
  if (extension.kind === "skill") {
    return `/${extension.name} `;
  }
  if (extension.kind === "agent") {
    return `Ask ${label} to `;
  }
  if (extension.kind === "mcp") {
    return `Use the ${label} MCP to `;
  }
  return `Use ${label} to `;
}

export function buildDemoConversationPrompt(
  extensions: ExtensionDescriptor[],
): string {
  const enabled = extensions.filter((extension) => extension.enabled);
  const enabledSummary = enabled.length
    ? enabled
        .map(
          (extension) =>
            `- ${formatExtensionKind(extension.kind)}: ${extensionDisplayName(extension)} (${extension.name})`,
        )
        .join("\n")
    : "- No enabled registry capabilities were returned by the catalog.";

  return [
    "Run the Brillio hackathon internal assistant demo end to end.",
    "",
    "Use the dynamically loaded registry capabilities discovered by the UI:",
    enabledSummary,
    "",
    "Demo steps:",
    "1. Briefly list the enabled agents, tools, skills, and MCP servers you can see from the registry catalog.",
    "2. Use HTML Report to create an HTML artifact titled Hackathon Readiness with sections for dynamic loading, harness separation, and judge flow.",
    '3. Use CSV Export to create rows_json for [{"capability":"agents","status":"dynamic","score":95},{"capability":"tools","status":"registry-loaded","score":98},{"capability":"skills","status":"discoverable","score":92}].',
    "4. Use PDF Report to create a PDF artifact titled Executive Demo Summary with three concise sections.",
    '5. Use Python Function to run internal_tools.python_examples:summarize_metrics with kwargs_json {"rows":[{"value":10},{"value":20},{"value":30}]}.',
    "6. Finish with a concise summary that includes generated artifact paths, the Python result, and any unavailable capability categories.",
  ].join("\n");
}

function renderExtensionPromptTemplate(
  template: string,
  extension: ExtensionDescriptor,
): string {
  const values: Record<string, string> = {
    category: extension.category ?? "",
    description: extension.description,
    display_name: extensionDisplayName(extension),
    entrypoint: extension.entrypoint ?? "",
    kind: formatExtensionKind(extension.kind),
    name: extension.name,
  };

  return template.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (match, key) =>
    key in values ? values[key]! : match,
  );
}

function metadataString(
  metadata: Record<string, unknown>,
  key: string,
): string | null {
  const value = metadata[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function metadataStringList(
  metadata: Record<string, unknown>,
  key: string,
): string[] {
  const value = metadata[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (item): item is string => typeof item === "string" && item.trim().length > 0,
  );
}
