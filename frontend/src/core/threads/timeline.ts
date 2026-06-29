export type RunTimelinePhase = "start" | "end" | "stream" | "event" | "error";

export type RunTimelineKind =
  | "run"
  | "chain"
  | "tool"
  | "model"
  | "custom"
  | "audit";

export type RunTimelineEvent = {
  id: string;
  timestamp: string;
  kind: RunTimelineKind;
  phase: RunTimelinePhase;
  name: string;
  label: string;
  summary: string | null;
};

export function compactRunTimelineEvents(
  events: RunTimelineEvent[],
  maxEvents = 200,
): RunTimelineEvent[] {
  return events.slice(-maxEvents);
}

export function readRunTimelineEvents(value: unknown): RunTimelineEvent[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isRunTimelineEvent);
}

export function getCapabilityAuditTimelineEvents(
  events: RunTimelineEvent[],
): RunTimelineEvent[] {
  return events.filter((event) => event.kind === "audit");
}

export function buildRunLifecycleEvent(
  phase: Extract<RunTimelinePhase, "start" | "end">,
  index: number,
): RunTimelineEvent {
  return {
    id: `run:${phase}:${index}`,
    timestamp: new Date().toISOString(),
    kind: "run",
    phase,
    name: "Run",
    label: phase === "start" ? "Run started" : "Run finished",
    summary: null,
  };
}

export function normalizeLangChainTimelineEvent(
  event: unknown,
  index: number,
): RunTimelineEvent | null {
  if (!isRecord(event)) {
    return null;
  }

  const eventName = readString(event.event) ?? "event";
  const name = readString(event.name) ?? formatEventName(eventName);
  const phase = phaseFromEventName(eventName);
  const kind = kindFromEventName(eventName);
  const data = isRecord(event.data) ? event.data : null;

  return {
    id: `${eventName}:${name}:${index}`,
    timestamp: new Date().toISOString(),
    kind,
    phase,
    name,
    label: `${formatEventName(name)} ${formatPhase(phase)}`,
    summary: summarizeEventData(data),
  };
}

export function normalizeCapabilityAuditTimelineEvent(
  event: unknown,
  index: number,
): RunTimelineEvent | null {
  if (!isRecord(event)) {
    return null;
  }

  const eventName = readString(event.event);
  if (
    eventName !== "on_tool_start" &&
    eventName !== "on_tool_end" &&
    eventName !== "on_tool_error"
  ) {
    return null;
  }

  const name = readString(event.name) ?? "unknown_tool";
  const phase = phaseFromEventName(eventName);
  const data = isRecord(event.data) ? event.data : null;

  return {
    id: `audit:${eventName}:${name}:${index}`,
    timestamp: new Date().toISOString(),
    kind: "audit",
    phase,
    name,
    label: `Capability ${formatEventName(name)} ${formatPhase(phase)}`,
    summary: summarizeEventData(data),
  };
}

export function normalizeCustomTimelineEvent(
  event: unknown,
  index: number,
): RunTimelineEvent | null {
  if (!isRecord(event)) {
    return null;
  }

  const type = readString(event.type);
  if (!type) {
    return null;
  }

  const message = readString(event.message);
  return {
    id: `custom:${type}:${index}`,
    timestamp: new Date().toISOString(),
    kind: "custom",
    phase: "event",
    name: type,
    label: formatEventName(type),
    summary: message ?? summarizeEventData(event),
  };
}

function phaseFromEventName(eventName: string): RunTimelinePhase {
  if (eventName.endsWith("_start")) {
    return "start";
  }
  if (eventName.endsWith("_end")) {
    return "end";
  }
  if (eventName.endsWith("_stream")) {
    return "stream";
  }
  if (eventName.endsWith("_error")) {
    return "error";
  }
  return "event";
}

function kindFromEventName(eventName: string): RunTimelineKind {
  if (eventName.includes("tool")) {
    return "tool";
  }
  if (eventName.includes("chat_model") || eventName.includes("llm")) {
    return "model";
  }
  if (eventName.includes("chain")) {
    return "chain";
  }
  return "custom";
}

function summarizeEventData(
  data: Record<string, unknown> | null,
): string | null {
  if (!data) {
    return null;
  }

  const output = readString(data.output);
  if (output) {
    return truncate(output);
  }
  const input = readString(data.input);
  if (input) {
    return truncate(input);
  }
  const chunk = readString(data.chunk);
  if (chunk) {
    return truncate(chunk);
  }

  const keys = Object.keys(data).filter((key) => data[key] !== undefined);
  return keys.length > 0 ? keys.slice(0, 4).join(", ") : null;
}

function formatPhase(phase: RunTimelinePhase): string {
  if (phase === "start") {
    return "started";
  }
  if (phase === "end") {
    return "finished";
  }
  if (phase === "stream") {
    return "streamed";
  }
  if (phase === "error") {
    return "failed";
  }
  return "event";
}

function formatEventName(value: string): string {
  return value
    .replace(/^on_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function truncate(value: string, maxLength = 140): string {
  return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isRunTimelineEvent(value: unknown): value is RunTimelineEvent {
  if (!isRecord(value)) {
    return false;
  }
  return (
    readString(value.id) !== null &&
    readString(value.timestamp) !== null &&
    isRunTimelineKind(value.kind) &&
    isRunTimelinePhase(value.phase) &&
    readString(value.name) !== null &&
    readString(value.label) !== null &&
    (value.summary === null || typeof value.summary === "string")
  );
}

function isRunTimelineKind(value: unknown): value is RunTimelineKind {
  return (
    value === "run" ||
    value === "chain" ||
    value === "tool" ||
    value === "model" ||
    value === "custom" ||
    value === "audit"
  );
}

function isRunTimelinePhase(value: unknown): value is RunTimelinePhase {
  return (
    value === "start" ||
    value === "end" ||
    value === "stream" ||
    value === "event" ||
    value === "error"
  );
}
