import { beforeEach, describe, expect, test, rs } from "@rstest/core";

rs.mock("@/core/api/fetcher", () => ({
  fetch: rs.fn(),
}));

rs.mock("@/core/config", () => ({
  getBackendBaseURL: () => "",
}));

import { fetch as fetcher } from "@/core/api/fetcher";
import { loadAuditExecutions } from "@/core/audit/api";

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

describe("loadAuditExecutions", () => {
  test("loads recent audit records with limit", async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse(200, {
        count: 1,
        path: "/tmp/audit.jsonl",
        records: [
          {
            event: "extension.execution",
            started_at: "2026-06-29T10:00:00Z",
            status: "success",
            extension: { kind: "tool", name: "html-report" },
            input_summary: { type: "mapping" },
            output_summary: { type: "string" },
            artifacts: ["report.html"],
          },
        ],
      }),
    );

    await expect(loadAuditExecutions({ limit: 10 })).resolves.toMatchObject({
      count: 1,
      records: [{ extension: { name: "html-report" } }],
    });
    expect(mockedFetch).toHaveBeenCalledWith(
      "/api/audit/executions?limit=10",
    );
  });

  test("defaults missing response fields", async () => {
    mockedFetch.mockResolvedValueOnce(jsonResponse(200, {}));

    await expect(loadAuditExecutions()).resolves.toEqual({
      count: 0,
      path: "",
      records: [],
    });
  });
});
