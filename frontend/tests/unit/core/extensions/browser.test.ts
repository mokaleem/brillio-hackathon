import { describe, expect, test } from "@rstest/core";

import {
  applyExtensionEnabledUpdate,
  filterExtensions,
  formatExtensionKind,
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
});
