export type ExtensionKind = "agent" | "mcp" | "tool" | "skill";

export interface ExtensionDescriptor {
  kind: ExtensionKind;
  name: string;
  enabled: boolean;
  source: string;
  entrypoint?: string | null;
  description: string;
  tags: string[];
  metadata: Record<string, unknown>;
  allowed_tools?: string[] | null;
  requires: string[];
  owner?: string | null;
  risk_level?: "low" | "medium" | "high" | null;
  display_name?: string | null;
  icon?: string | null;
  category?: string | null;
}

export interface ExtensionsResponse {
  extensions: ExtensionDescriptor[];
  count: number;
}

export interface ExtensionValidateResponse {
  valid: boolean;
  count: number;
  errors: string[];
  warnings: string[];
}

export interface ExtensionHealthResponse {
  valid: boolean;
  count: number;
  manifests: string[];
  errors: string[];
  warnings: string[];
}

export interface ExtensionUpdateResponse {
  extension: ExtensionDescriptor;
}
