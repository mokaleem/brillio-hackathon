import { beforeEach, describe, expect, test, rs } from "@rstest/core";

rs.mock("@/core/api/fetcher", () => ({
  fetch: rs.fn(),
}));

rs.mock("@/core/config", () => ({
  getBackendBaseURL: () => "",
}));

import { fetch as fetcher } from "@/core/api/fetcher";
import { exportAuditEvidence, loadAuditExecutions } from "@/core/audit/api";

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
    expect(mockedFetch).toHaveBeenCalledWith("/api/audit/executions?limit=10");
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

describe("exportAuditEvidence", () => {
  test("exports compliance evidence with limit", async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse(200, {
        schema_version: 1,
        generated_at: "2026-06-29T10:00:00Z",
        source_path: "/tmp/audit.jsonl",
        summary: {
          total_records: 1,
          status_counts: { success: 1 },
          extension_counts: { "html-report": 1 },
          artifact_count: 1,
        },
        records: [{ event: "extension.execution", status: "success" }],
      }),
    );

    await expect(exportAuditEvidence({ limit: 100 })).resolves.toMatchObject({
      schema_version: 1,
      summary: { total_records: 1, artifact_count: 1 },
    });
    expect(mockedFetch).toHaveBeenCalledWith("/api/audit/evidence?limit=100");
  });

  test("defaults missing evidence response fields", async () => {
    mockedFetch.mockResolvedValueOnce(jsonResponse(200, {}));

    await expect(exportAuditEvidence()).resolves.toEqual({
      schema_version: 1,
      generated_at: "",
      source_path: "",
      summary: {
        total_records: 0,
        status_counts: {},
        extension_counts: {},
        artifact_count: 0,
      },
      records: [],
    });
  });
});
