import path from "node:path";

import { expect, test, type Page, type Route } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

const evidenceDir = path.resolve(process.cwd(), "../docs/pr-evidence");
const threadId = "hackathon-evidence-thread";

const extensions = [
  {
    kind: "agent",
    name: "reporting-agent",
    enabled: true,
    source: "registries/demo_extensions.json",
    entrypoint: "internal_agents.reporting:agent",
    description: "Coordinates executive-ready reporting workflows.",
    tags: ["demo", "reporting"],
    metadata: {},
    requires: ["html-report", "pdf-report"],
    owner: "hackathon",
    risk_level: "medium",
    display_name: "Reporting Agent",
  },
  {
    kind: "tool",
    name: "html-report",
    enabled: true,
    source: "registries/demo_extensions.json",
    entrypoint: "internal_tools.report_artifacts:generate_html_report",
    description: "Generates styled HTML reports.",
    tags: ["artifact", "html"],
    metadata: {},
    requires: [],
    owner: "hackathon",
    risk_level: "low",
    display_name: "HTML Report",
  },
  {
    kind: "tool",
    name: "csv-export",
    enabled: true,
    source: "registries/demo_extensions.json",
    entrypoint: "internal_tools.report_artifacts:generate_csv",
    description: "Exports structured rows as CSV.",
    tags: ["artifact", "csv"],
    metadata: {},
    requires: [],
    owner: "hackathon",
    risk_level: "low",
    display_name: "CSV Export",
  },
  {
    kind: "tool",
    name: "pdf-report",
    enabled: true,
    source: "registries/demo_extensions.json",
    entrypoint: "internal_tools.report_artifacts:generate_pdf_report",
    description: "Creates concise PDF summaries.",
    tags: ["artifact", "pdf"],
    metadata: {},
    requires: [],
    owner: "hackathon",
    risk_level: "medium",
    display_name: "PDF Report",
  },
  {
    kind: "tool",
    name: "python-function",
    enabled: true,
    source: "registries/demo_extensions.json",
    entrypoint: "internal_tools.python_runner:execute_python_function",
    description: "Runs approved Python functions with JSON kwargs.",
    tags: ["python", "execution"],
    metadata: {},
    requires: [],
    owner: "hackathon",
    risk_level: "high",
    display_name: "Python Function",
  },
  {
    kind: "skill",
    name: "market-research",
    enabled: true,
    source: "registries/demo_extensions.json",
    description: "Research synthesis prompt skill.",
    tags: ["research"],
    metadata: {},
    requires: [],
    owner: "hackathon",
    risk_level: "low",
    display_name: "Market Research",
  },
];

const timelineEvents = [
  {
    id: "run:start:0",
    timestamp: "2026-06-30T15:00:00Z",
    kind: "run",
    phase: "start",
    name: "Run",
    label: "Run started",
    summary: null,
  },
  {
    id: "audit:on_tool_start:html-report:1",
    timestamp: "2026-06-30T15:00:01Z",
    kind: "audit",
    phase: "start",
    name: "html-report",
    label: "Capability Html Report started",
    summary: "input keys: title, sections",
  },
  {
    id: "audit:on_tool_end:pdf-report:2",
    timestamp: "2026-06-30T15:00:05Z",
    kind: "audit",
    phase: "end",
    name: "pdf-report",
    label: "Capability Pdf Report finished",
    summary: "artifact pdf-report-hackathon.pdf",
  },
  {
    id: "run:end:3",
    timestamp: "2026-06-30T15:00:06Z",
    kind: "run",
    phase: "end",
    name: "Run",
    label: "Run finished",
    summary: null,
  },
];

const evidenceThreadValues = {
  title: "Hackathon release evidence",
  messages: [
    {
      type: "human",
      id: "evidence-human",
      content: [
        {
          type: "text",
          text: "Run the Brillio hackathon internal assistant demo.",
        },
      ],
    },
    {
      type: "ai",
      id: "evidence-ai",
      content:
        "Generated HTML, CSV, PDF, and Python summary artifacts for the internal assistant release.",
    },
  ],
  artifacts: [
    "/mnt/data/html-report-hackathon.html",
    "/mnt/data/csv-export-hackathon.csv",
    "/mnt/data/pdf-report-hackathon.pdf",
  ],
  run_timeline_events: timelineEvents,
};

test("captures hackathon release evidence screenshots", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  mockLangGraphAPI(page, {
    threads: [
      {
        thread_id: threadId,
        title: "Hackathon release evidence",
        updated_at: "2026-06-30T15:00:00Z",
      },
    ],
  });
  await mockExtensions(page);
  await mockEvidenceThread(page);

  await page.goto("/workspace/extensions");
  await expect(
    page.getByRole("heading", { name: "Extension Registry" }),
  ).toBeVisible();
  const observability = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Demo Observability" }),
  });
  await expect(observability.getByText("Needs Attention")).toBeVisible();
  await expect(page.getByText("Reporting Agent")).toBeVisible();
  await page.screenshot({
    path: path.join(evidenceDir, "hackathon-extension-registry.png"),
    fullPage: true,
  });
  await observability.screenshot({
    path: path.join(evidenceDir, "hackathon-demo-observability.png"),
  });

  await page.getByRole("button", { name: /^Import$/ }).click();
  await page.getByLabel("Registry JSON").fill(
    JSON.stringify({
      version: 1,
      extensions: [
        {
          kind: "tool",
          name: "forecast-export",
          enabled: true,
          source: "registry",
          entrypoint: "internal_tools.forecast:export",
          description:
            "Exports a forecast table for the imported registry demo.",
          tags: ["forecast"],
          metadata: {},
          requires: [],
          owner: "finance-demo",
          risk_level: "medium",
          display_name: "Forecast Export",
        },
      ],
    }),
  );
  await page.getByRole("button", { name: /Preview/i }).click();
  await expect(
    page.getByText("Forecast Export", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Import Extension Registry").screenshot({
    path: path.join(evidenceDir, "hackathon-import-preview.png"),
  });

  await page.goto("/workspace/chats/new");
  const textarea = page.getByPlaceholder(/how can i assist you/i);
  await expect(textarea).toBeVisible();
  await page.getByRole("button", { name: /Capabilities/i }).click();
  await expect(
    page.getByText("Hackathon demo flow", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(evidenceDir, "hackathon-chat-capabilities.png"),
    fullPage: true,
  });

  await page.goto(`/workspace/chats/${threadId}`);
  await expect(page.getByTestId("artifact-trigger")).toBeVisible();
  await page.getByRole("button", { name: "Open run timeline" }).click();
  await expect(
    page.getByRole("heading", { name: "Run Timeline" }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(evidenceDir, "hackathon-run-trace.png"),
    fullPage: true,
  });
  await page.keyboard.press("Escape");

  await page.getByTestId("artifact-trigger").click();
  await expect(page.getByText("html-report-hackathon.html")).toBeVisible();
  await page.screenshot({
    path: path.join(evidenceDir, "hackathon-artifact-center.png"),
    fullPage: true,
  });
});

async function mockExtensions(page: Page) {
  await page.route("**/api/audit/executions**", async (route) => {
    if (route.request().method() !== "GET") {
      return route.fallback();
    }
    return fulfillJson(route, {
      count: 2,
      path: "D:/apps/brillio-hackathon/backend/.deer-flow/audit/executions.jsonl",
      records: [
        {
          event: "extension.execution",
          started_at: "2026-06-30T15:00:01Z",
          ended_at: "2026-06-30T15:00:02Z",
          duration_ms: 840,
          status: "success",
          extension: {
            kind: "tool",
            name: "html-report",
            display_name: "HTML Report",
            source: "registry",
            risk_level: "low",
            provenance: { source_name: "finance-demo" },
          },
          input_summary: { type: "mapping", size: 2, keys: ["title"] },
          output_summary: { type: "string", length: 72 },
          artifacts: ["reports/hackathon-readiness.html"],
          error: null,
        },
        {
          event: "extension.execution",
          started_at: "2026-06-30T15:01:00Z",
          ended_at: "2026-06-30T15:01:00Z",
          duration_ms: 41,
          status: "error",
          extension: {
            kind: "tool",
            name: "python-function",
            display_name: "Python Function",
            source: "registry",
            risk_level: "high",
          },
          input_summary: { type: "mapping", size: 3, keys: ["entrypoint"] },
          output_summary: { type: "none" },
          artifacts: [],
          error: { type: "RuntimeError", message: "Function not allowlisted" },
        },
      ],
    });
  });

  await page.route("**/api/extensions**", async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (request.method() === "GET" && pathname === "/api/extensions") {
      return fulfillJson(route, {
        count: extensions.length,
        extensions,
      });
    }
    if (request.method() === "GET" && pathname === "/api/extensions/health") {
      return fulfillJson(route, {
        valid: true,
        count: extensions.length,
        manifests: ["registries/demo_extensions.json"],
        errors: [],
        warnings: ["External registries should be reviewed before import."],
      });
    }
    if (
      request.method() === "POST" &&
      pathname === "/api/extensions/import/preview"
    ) {
      const extension = {
        ...extensions[1],
        name: "forecast-export",
        display_name: "Forecast Export",
        source: "registry",
        entrypoint: "internal_tools.forecast:export",
        owner: "finance-demo",
        tags: ["forecast"],
        risk_level: "medium",
      };
      return fulfillJson(route, {
        valid: true,
        count: 1,
        extensions: [extension],
        errors: [],
        warnings: ["Imported registry source: registry"],
        duplicates: [],
        changes: [
          {
            key: "tool:forecast-export",
            action: "add",
            extension,
            existing: null,
            reason: null,
          },
        ],
      });
    }
    return route.fallback();
  });
}

async function mockEvidenceThread(page: Page) {
  await page.route(`**/api/langgraph/threads/${threadId}/history`, (route) =>
    fulfillJson(route, [
      {
        values: evidenceThreadValues,
        next: [],
        metadata: {},
        created_at: "2026-06-30T15:00:00Z",
        parent_config: null,
      },
    ]),
  );
  await page.route(`**/api/langgraph/threads/${threadId}/state`, (route) =>
    fulfillJson(route, {
      values: evidenceThreadValues,
      next: [],
      metadata: {},
      created_at: "2026-06-30T15:00:00Z",
    }),
  );
  await page.route("**/api/threads/**/artifacts/**", (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith(".html")) {
      return route.fulfill({
        status: 200,
        contentType: "text/html",
        body: "<h1>Hackathon Readiness Report</h1><p>Registry and artifacts verified.</p>",
      });
    }
    if (pathname.endsWith(".csv")) {
      return route.fulfill({
        status: 200,
        contentType: "text/csv",
        body: "metric,value\nreadiness,ready\nartifacts,3\n",
      });
    }
    if (pathname.endsWith(".pdf")) {
      return route.fulfill({
        status: 200,
        contentType: "application/pdf",
        body: "%PDF-1.4\n% evidence placeholder\n",
      });
    }
    return route.fallback();
  });
}

function fulfillJson(route: Route, body: unknown) {
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}
