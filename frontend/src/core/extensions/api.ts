import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { ExtensionKind, ExtensionsResponse } from "./types";

export class ExtensionRequestError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ExtensionRequestError";
    this.status = status;
  }
}

export async function loadExtensions(options?: {
  kind?: ExtensionKind;
}): Promise<ExtensionsResponse> {
  const params = new URLSearchParams();
  if (options?.kind) {
    params.set("kind", options.kind);
  }
  const query = params.toString();
  const response = await fetch(
    `${getBackendBaseURL()}/api/extensions${query ? `?${query}` : ""}`,
  );
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: unknown;
    };
    throw new ExtensionRequestError(
      typeof body.detail === "string" ? body.detail : "Failed to load extensions",
      response.status,
    );
  }
  const data = (await response.json()) as Partial<ExtensionsResponse>;
  return {
    extensions: data.extensions ?? [],
    count: data.count ?? 0,
  };
}
