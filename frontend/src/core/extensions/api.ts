import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type {
  ExtensionKind,
  ExtensionUpdateResponse,
  ExtensionValidateResponse,
  ExtensionsResponse,
} from "./types";

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
  return requestExtensions(buildExtensionsPath("/api/extensions", options));
}

export async function validateExtensions(): Promise<ExtensionValidateResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/extensions/validate`, {
    method: "POST",
  });
  await assertOk(response, "Failed to validate extensions");
  const data = (await response.json()) as Partial<ExtensionValidateResponse>;
  return {
    valid: data.valid ?? false,
    count: data.count ?? 0,
    errors: data.errors ?? [],
  };
}

export async function reloadExtensions(options?: {
  kind?: ExtensionKind;
}): Promise<ExtensionsResponse> {
  return requestExtensions(buildExtensionsPath("/api/extensions/reload", options), {
    method: "POST",
  });
}

export async function updateExtensionEnabled(
  kind: ExtensionKind,
  name: string,
  enabled: boolean,
): Promise<ExtensionUpdateResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/extensions/${kind}/${encodeURIComponent(name)}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ enabled }),
    },
  );
  await assertOk(response, "Failed to update extension");
  return response.json() as Promise<ExtensionUpdateResponse>;
}

async function requestExtensions(
  path: string,
  init?: RequestInit,
): Promise<ExtensionsResponse> {
  const url = `${getBackendBaseURL()}${path}`;
  const response = init ? await fetch(url, init) : await fetch(url);
  await assertOk(response, "Failed to load extensions");
  const data = (await response.json()) as Partial<ExtensionsResponse>;
  return {
    extensions: data.extensions ?? [],
    count: data.count ?? 0,
  };
}

function buildExtensionsPath(
  pathname: "/api/extensions" | "/api/extensions/reload",
  options?: { kind?: ExtensionKind },
) {
  const params = new URLSearchParams();
  if (options?.kind) {
    params.set("kind", options.kind);
  }
  const query = params.toString();
  return `${pathname}${query ? `?${query}` : ""}`;
}

async function assertOk(response: Response, fallbackMessage: string) {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: unknown;
    };
    throw new ExtensionRequestError(
      typeof body.detail === "string" ? body.detail : fallbackMessage,
      response.status,
    );
  }
}
