export interface AuditExecutionRecord {
  event: string;
  started_at: string;
  ended_at?: string | null;
  duration_ms?: number | null;
  status: "success" | "error" | string;
  extension: {
    kind?: string | null;
    name?: string | null;
    display_name?: string | null;
    source?: string | null;
    entrypoint?: string | null;
    risk_level?: "low" | "medium" | "high" | string | null;
    owner?: string | null;
    provenance?: {
      source_name?: string | null;
      source_path?: string | null;
      source_url?: string | null;
      registry_version?: number | null;
      descriptor_hash?: string | null;
      imported_at?: string | null;
    } | null;
  };
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  artifacts: string[];
  error?: {
    type?: string | null;
    message?: string | null;
  } | null;
}

export interface AuditExecutionsResponse {
  records: AuditExecutionRecord[];
  count: number;
  path: string;
}

export interface AuditEvidenceSummary {
  total_records: number;
  status_counts: Record<string, number>;
  extension_counts: Record<string, number>;
  artifact_count: number;
}

export interface AuditEvidenceExport {
  schema_version: number;
  generated_at: string;
  source_path: string;
  summary: AuditEvidenceSummary;
  records: AuditExecutionRecord[];
}
