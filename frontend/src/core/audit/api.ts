import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { AuditExecutionsResponse } from "./types";

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
