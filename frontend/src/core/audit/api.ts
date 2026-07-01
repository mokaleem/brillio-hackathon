import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { AuditEvidenceExport, AuditExecutionsResponse } from "./types";

export async function loadAuditExecutions(options?: {
  limit?: number;
}): Promise<AuditExecutionsResponse> {
  const params = new URLSearchParams();
  if (options?.limit) {
    params.set("limit", String(options.limit));
  }
  const query = params.toString();
  const response = await fetch(
    `${getBackendBaseURL()}/api/audit/executions${query ? `?${query}` : ""}`,
  );
  if (!response.ok) {
    throw new Error("Failed to load audit executions");
  }
  const data = (await response.json()) as Partial<AuditExecutionsResponse>;
  return {
    records: data.records ?? [],
    count: data.count ?? 0,
    path: data.path ?? "",
  };
}

export async function exportAuditEvidence(options?: {
  limit?: number;
}): Promise<AuditEvidenceExport> {
  const params = new URLSearchParams();
  if (options?.limit) {
    params.set("limit", String(options.limit));
  }
  const query = params.toString();
  const response = await fetch(
    `${getBackendBaseURL()}/api/audit/evidence${query ? `?${query}` : ""}`,
  );
  if (!response.ok) {
    throw new Error("Failed to export audit evidence");
  }
  const data = (await response.json()) as Partial<AuditEvidenceExport>;
  return {
    schema_version: data.schema_version ?? 1,
    generated_at: data.generated_at ?? "",
    source_path: data.source_path ?? "",
    summary: {
      total_records: data.summary?.total_records ?? 0,
      status_counts: data.summary?.status_counts ?? {},
      extension_counts: data.summary?.extension_counts ?? {},
      artifact_count: data.summary?.artifact_count ?? 0,
    },
    records: data.records ?? [],
  };
}
