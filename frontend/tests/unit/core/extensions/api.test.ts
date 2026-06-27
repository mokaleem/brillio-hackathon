import { beforeEach, describe, expect, test, rs } from "@rstest/core";

rs.mock("@/core/api/fetcher", () => ({
  fetch: rs.fn(),
}));

rs.mock("@/core/config", () => ({
  getBackendBaseURL: () => "",
}));

import { fetch as fetcher } from "@/core/api/fetcher";
import { ExtensionRequestError, loadExtensions } from "@/core/extensions/api";

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
