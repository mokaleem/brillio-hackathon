import { describe, expect, test } from "@rstest/core";

import {
  buildRunLifecycleEvent,
  compactRunTimelineEvents,
  normalizeCustomTimelineEvent,
  normalizeLangChainTimelineEvent,
  readRunTimelineEvents,
} from "@/core/threads/timeline";

describe("run timeline helpers", () => {
  test("builds run lifecycle events", () => {
    expect(buildRunLifecycleEvent("start", 0)).toMatchObject({
      id: "run:start:0",
      kind: "run",
      phase: "start",
      label: "Run started",
    });
  });

  test("normalizes LangChain tool events", () => {
    expect(
      normalizeLangChainTimelineEvent(
        {
          event: "on_tool_end",
          name: "html_report",
          data: { output: "HTML report generated" },
        },
        7,
      ),
    ).toMatchObject({
      id: "on_tool_end:html_report:7",
      kind: "tool",
      phase: "end",
      name: "html_report",
      label: "Html Report finished",
      summary: "HTML report generated",
    });
  });

  test("normalizes custom orchestration events", () => {
    expect(
      normalizeCustomTimelineEvent(
        { type: "llm_retry", message: "Retrying model request" },
        3,
      ),
    ).toMatchObject({
      id: "custom:llm_retry:3",
      kind: "custom",
      phase: "event",
      label: "Llm Retry",
      summary: "Retrying model request",
    });
  });

  test("reads and compacts persisted timeline events", () => {
    const first = buildRunLifecycleEvent("start", 0);
    const second = buildRunLifecycleEvent("end", 1);

    expect(
      readRunTimelineEvents([
        first,
        { id: "bad", kind: "run" },
        second,
        null,
      ]),
    ).toEqual([first, second]);
    expect(compactRunTimelineEvents([first, second], 1)).toEqual([second]);
  });
});
