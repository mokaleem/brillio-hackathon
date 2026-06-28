import { beforeEach, describe, expect, test, rs } from "@rstest/core";

rs.mock("@/core/api/fetcher", () => ({
  fetch: rs.fn(),
}));

rs.mock("@/core/config", () => ({
  getBackendBaseURL: () => "",
}));

import { fetch as fetcher } from "@/core/api/fetcher";
import {
  loadExtensionHealth,
  loadExtensions,
  reloadExtensions,
  updateExtensionEnabled,
  validateExtensions,
} from "@/core/extensions/api";

const mockedFetch = rs.mocked(fetcher);

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  mockedFetch.mockReset();
});

describe("loadExtensions", () => {
  test("returns extension catalog data on 200", async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse(200, {
        count: 1,
        extensions: [
          {
            kind: "tool",
            name: "html-report",
            enabled: true,
            source: "local",
            entrypoint: "internal_tools.reporting:html_report_tool",
            description: "Generate reports",
            tags: ["reporting"],
            metadata: {},
            requires: [],
          },
        ],
      }),
    );

    await expect(loadExtensions()).resolves.toMatchObject({
      count: 1,
      extensions: [{ name: "html-report", kind: "tool" }],
    });
    expect(mockedFetch).toHaveBeenCalledWith("/api/extensions");
  });

  test("adds kind query when filtering", async () => {
    mockedFetch.mockResolvedValueOnce(jsonResponse(200, { count: 0, extensions: [] }));

    await loadExtensions({ kind: "skill" });

    expect(mockedFetch).toHaveBeenCalledWith("/api/extensions?kind=skill");
  });

  test("throws ExtensionRequestError on non-2xx responses", async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse(500, { detail: "Registry unavailable" }),
    );

    await expect(loadExtensions()).rejects.toMatchObject({
      name: "ExtensionRequestError",
      status: 500,
      message: "Registry unavailable",
    });
  });
});

describe("extension management api", () => {
  test("validateExtensions posts to the validate endpoint", async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse(200, { valid: true, count: 2, errors: [] }),
    );

    await expect(validateExtensions()).resolves.toEqual({
      valid: true,
      count: 2,
      errors: [],
      warnings: [],
    });
    expect(mockedFetch).toHaveBeenCalledWith("/api/extensions/validate", {
      method: "POST",
    });
  });

  test("loadExtensionHealth reads registry health", async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse(200, {
        valid: false,
        count: 1,
        manifests: ["/repo/registry.json"],
        errors: ["bad MCP"],
        warnings: ["missing prompt template"],
      }),
    );

    await expect(loadExtensionHealth()).resolves.toEqual({
      valid: false,
      count: 1,
      manifests: ["/repo/registry.json"],
      errors: ["bad MCP"],
      warnings: ["missing prompt template"],
    });
    expect(mockedFetch).toHaveBeenCalledWith("/api/extensions/health");
  });

  test("reloadExtensions posts to the reload endpoint", async () => {
    mockedFetch.mockResolvedValueOnce(jsonResponse(200, { count: 0, extensions: [] }));

    await reloadExtensions({ kind: "tool" });

    expect(mockedFetch).toHaveBeenCalledWith("/api/extensions/reload?kind=tool", {
      method: "POST",
    });
  });

  test("updateExtensionEnabled writes enabled state", async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse(200, {
        extension: {
          kind: "skill",
          name: "market-research",
          enabled: true,
          source: "local",
          description: "",
          tags: [],
          metadata: {},
          requires: [],
        },
      }),
    );

    await expect(
      updateExtensionEnabled("skill", "market-research", true),
    ).resolves.toMatchObject({
      extension: { name: "market-research", enabled: true },
    });
    expect(mockedFetch).toHaveBeenCalledWith(
      "/api/extensions/skill/market-research",
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ enabled: true }),
      },
    );
  });
});
