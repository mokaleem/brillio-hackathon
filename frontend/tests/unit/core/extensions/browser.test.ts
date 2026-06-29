import { describe, expect, test } from "@rstest/core";

import {
  applyExtensionEnabledUpdate,
  buildExtensionPrompt,
  buildDemoConversationPrompt,
  extensionDisplayName,
  filterExtensions,
  formatExtensionKind,
  getExtensionExamplePrompts,
  getExtensionPromptTemplate,
  summarizeExtensions,
} from "@/core/extensions/browser";
import type { ExtensionDescriptor } from "@/core/extensions/types";

const extensions: ExtensionDescriptor[] = [
  {
    kind: "agent",
    name: "finance-analyst",
    enabled: true,
    source: "local",
    entrypoint: "internal_agents.finance:create_agent",
    description: "Finance research agent",
    tags: ["finance", "reporting"],
    metadata: {},
    requires: ["market-data-tool"],
    risk_level: "medium",
    display_name: "Finance Analyst",
  },
  {
    kind: "tool",
    name: "market-data-tool",
    enabled: false,
    source: "registry",
    entrypoint: "company_tools.market:data_tool",
    description: "Pulls pricing signals",
    tags: ["markets"],
    metadata: {},
    requires: [],
    owner: "treasury",
    risk_level: "high",
  },
  {
    kind: "skill",
    name: "quarterly-report",
    enabled: true,
    source: "local",
    entrypoint: "internal_skills/quarterly-report",
    description: "Creates finance report drafts",
    tags: ["writing"],
    metadata: {},
    requires: [],
    category: "reporting",
  },
];

describe("extension browser helpers", () => {
  test("summarizes extension counts by state and kind", () => {
    expect(summarizeExtensions(extensions)).toEqual({
      total: 3,
      enabled: 2,
      disabled: 1,
      byKind: {
        agent: 1,
        mcp: 0,
        tool: 1,
        skill: 1,
      },
    });
  });

  test("filters by kind, status, and searchable fields", () => {
    expect(
      filterExtensions(extensions, {
        kind: "tool",
        status: "disabled",
        query: "treasury",
      }).map((extension) => extension.name),
    ).toEqual(["market-data-tool"]);

    expect(
      filterExtensions(extensions, {
        kind: "all",
        status: "enabled",
        query: "reporting",
      }).map((extension) => extension.name),
    ).toEqual(["finance-analyst", "quarterly-report"]);
  });

  test("replaces the descriptor updated by the management api", () => {
    const updated: ExtensionDescriptor = { ...extensions[1]!, enabled: true };

    expect(applyExtensionEnabledUpdate(extensions, updated)).toEqual([
      extensions[0],
      updated,
      extensions[2],
    ]);
  });

  test("formats MCP as an acronym", () => {
    expect(formatExtensionKind("mcp")).toBe("MCP");
    expect(formatExtensionKind("agent")).toBe("Agent");
  });

  test("uses display name as the capability label", () => {
    expect(extensionDisplayName(extensions[0]!)).toBe("Finance Analyst");
    expect(extensionDisplayName(extensions[1]!)).toBe("market-data-tool");
  });

  test("builds prompts from registry prompt templates", () => {
    const extension: ExtensionDescriptor = {
      ...extensions[1]!,
      display_name: "Market Data",
      metadata: {
        prompt_template:
          "Use {{display_name}} ({{kind}}) to inspect {{category}} for ",
      },
      category: "Treasury",
    };

    expect(buildExtensionPrompt(extension)).toBe(
      "Use Market Data (Tool) to inspect Treasury for ",
    );
  });

  test("uses first example prompt when no prompt template exists", () => {
    const extension: ExtensionDescriptor = {
      ...extensions[1]!,
      metadata: {
        example_prompts: [
          "Pull market data for the current pipeline.",
          "Compare market data by region.",
        ],
      },
    };

    expect(buildExtensionPrompt(extension)).toBe(
      "Pull market data for the current pipeline.",
    );
    expect(getExtensionExamplePrompts(extension)).toEqual([
      "Pull market data for the current pipeline.",
      "Compare market data by region.",
    ]);
  });

  test("reads prompt template metadata for management display", () => {
    const extension: ExtensionDescriptor = {
      ...extensions[1]!,
      metadata: {
        prompt_template: "Use {{display_name}} to ",
      },
    };

    expect(getExtensionPromptTemplate(extension)).toBe(
      "Use {{display_name}} to ",
    );
    expect(getExtensionExamplePrompts(extension)).toEqual([]);
  });

  test("falls back to kind-specific prompts", () => {
    expect(buildExtensionPrompt(extensions[0]!)).toBe("Ask Finance Analyst to ");
    expect(buildExtensionPrompt(extensions[2]!)).toBe("/quarterly-report ");
    expect(buildExtensionPrompt(extensions[1]!)).toBe("Use market-data-tool to ");
  });

  test("builds deterministic hackathon demo prompt from enabled capabilities", () => {
    const prompt = buildDemoConversationPrompt(extensions);

    expect(prompt).toContain("Run the Brillio hackathon internal assistant demo");
    expect(prompt).toContain("Agent: Finance Analyst (finance-analyst)");
    expect(prompt).toContain("Skill: quarterly-report (quarterly-report)");
    expect(prompt).not.toContain("market-data-tool (market-data-tool)");
    expect(prompt).toContain("Use HTML Report to create an HTML artifact");
    expect(prompt).toContain(
      "internal_tools.python_examples:summarize_metrics",
    );
  });
});
