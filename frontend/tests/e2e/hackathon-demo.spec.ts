import { expect, test, type Page, type Route } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

type ExtensionKind = "agent" | "mcp" | "tool" | "skill";

type MockExtension = {
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
  provenance?: {
    imported_at: string;
    descriptor_hash: string;
    registry_version: number;
    source_name?: string | null;
    source_path?: string | null;
    source_url?: string | null;
  } | null;
};

const demoExtensions: MockExtension[] = [
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
    metadata: {
      prompt_template: "Use HTML Report to create {{display_name}}.",
    },
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
  {
    kind: "mcp",
    name: "local-docs",
    enabled: false,
    source: "registries/demo_extensions.json",
    description: "Local documentation search MCP server.",
    tags: ["docs"],
    metadata: {},
    requires: [],
    owner: "hackathon",
    risk_level: "medium",
    display_name: "Local Docs",
  },
];

const importedExtension: MockExtension = {
  kind: "tool",
  name: "forecast-export",
  enabled: true,
  source: "external://hackathon-forecast-registry",
  entrypoint: "internal_tools.forecast:export",
  description: "Exports a forecast table for the imported registry demo.",
  tags: ["forecast", "external"],
  metadata: {
    example_prompts: ["Use Forecast Export to create a quarterly forecast."],
  },
  requires: [],
  owner: "finance-demo",
  risk_level: "medium",
  display_name: "Forecast Export",
  provenance: {
    imported_at: "2026-06-29T16:00:00Z",
    descriptor_hash:
      "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    registry_version: 1,
    source_name: "finance-demo",
    source_url: "https://registry.example.com/forecast.json",
  },
};

const blockedExtension: MockExtension = {
  kind: "tool",
  name: "shell-tool",
  enabled: true,
  source: "registry",
  entrypoint: "os:system",
  description: "Attempts to execute an unapproved shell function.",
  tags: ["blocked"],
  metadata: {},
  requires: [],
  owner: "security-demo",
  risk_level: "high",
  display_name: "Shell Tool",
};

function mockExtensionRegistryAPI(page: Page) {
  let extensions = [...demoExtensions];
  const enablementUpdates: {
    kind: ExtensionKind;
    name: string;
    enabled: boolean;
  }[] = [];

  void page.route("**/api/audit/executions**", async (route) => {
    if (route.request().method() !== "GET") {
      return route.fallback();
    }
    return fulfillJson(route, {
      count: 2,
      path: "D:/apps/brillio-hackathon/backend/.deer-flow/audit/executions.jsonl",
      records: [
        {
          event: "extension.execution",
          started_at: "2026-06-29T18:00:00Z",
          ended_at: "2026-06-29T18:00:01Z",
          duration_ms: 840,
          status: "success",
          extension: {
            kind: "tool",
            name: "html-report",
            display_name: "HTML Report",
            source: "registry",
            risk_level: "low",
            provenance: {
              source_name: "finance-demo",
            },
          },
          input_summary: { type: "mapping", size: 2, keys: ["title"] },
          output_summary: { type: "string", length: 72 },
          artifacts: ["reports/hackathon-readiness.html"],
          error: null,
        },
        {
          event: "extension.execution",
          started_at: "2026-06-29T18:01:00Z",
          ended_at: "2026-06-29T18:01:00Z",
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

  void page.route("**/api/extensions**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;

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
        manifests: [
          "registries/demo_extensions.json",
          "registries/imported_extensions.json",
        ],
        errors: [],
        warnings: ["External registries should be reviewed before import."],
      });
    }

    if (
      request.method() === "POST" &&
      pathname === "/api/extensions/validate"
    ) {
      return fulfillJson(route, {
        valid: true,
        count: extensions.length,
        errors: [],
        warnings: [],
      });
    }

    if (
      request.method() === "POST" &&
      pathname === "/api/extensions/import/preview"
    ) {
      const body = request.postDataJSON() as { manifest_json?: string };
      if (body.manifest_json?.includes("shell-tool")) {
        return fulfillJson(route, {
          valid: false,
          count: 1,
          extensions: [blockedExtension],
          changes: [
            {
              key: "tool:shell-tool",
              action: "add",
              extension: blockedExtension,
              existing: null,
              reason: null,
            },
          ],
          errors: [
            "tool:shell-tool entrypoint 'os:system' is not allowed by DEERFLOW_EXTENSION_IMPORT_ENTRYPOINT_PREFIXES.",
          ],
          warnings: [
            "tool:shell-tool comes from source 'registry'. Review registry trust before importing.",
            "tool:shell-tool is marked high risk; review before enabling in production.",
          ],
          duplicates: [],
        });
      }
      expect(body.manifest_json).toContain("forecast-export");
      return fulfillJson(route, {
        valid: true,
        count: 1,
        extensions: [importedExtension],
        changes: [
          {
            key: "tool:forecast-export",
            action: "add",
            extension: importedExtension,
            existing: null,
            reason: null,
          },
        ],
        errors: [],
        warnings: [
          "Imported registry source: external://hackathon-forecast-registry",
        ],
        duplicates: [],
      });
    }

    if (request.method() === "POST" && pathname === "/api/extensions/import") {
      const body = request.postDataJSON() as { selected?: string[] };
      expect(body.selected).toContain("tool:forecast-export");
      extensions = [
        ...extensions.filter(
          (extension) =>
            `${extension.kind}:${extension.name}` !== "tool:forecast-export",
        ),
        importedExtension,
      ];
      return fulfillJson(route, {
        count: extensions.length,
        extensions,
      });
    }

    if (
      request.method() === "DELETE" &&
      pathname === "/api/extensions/imported/tool/forecast-export"
    ) {
      extensions = extensions.filter(
        (extension) =>
          `${extension.kind}:${extension.name}` !== "tool:forecast-export",
      );
      return fulfillJson(route, {
        count: extensions.length,
        extensions,
      });
    }

    if (request.method() === "POST" && pathname === "/api/extensions/reload") {
      return fulfillJson(route, {
        count: extensions.length,
        extensions,
      });
    }

    if (request.method() === "PUT" && pathname.startsWith("/api/extensions/")) {
      const [, , , kind, name] = pathname.split("/");
      const body = request.postDataJSON() as { enabled?: boolean };
      expect(["agent", "mcp", "tool", "skill"]).toContain(kind);
      expect(name).toBeTruthy();
      expect(typeof body.enabled).toBe("boolean");
      if (
        !kind ||
        !["agent", "mcp", "tool", "skill"].includes(kind) ||
        !name ||
        typeof body.enabled !== "boolean"
      ) {
        return route.abort();
      }
      const enabled = body.enabled;
      enablementUpdates.push({
        kind: kind as ExtensionKind,
        name,
        enabled,
      });
      const updated = extensions.find(
        (extension) => extension.kind === kind && extension.name === name,
      );
      expect(updated).toBeTruthy();
      extensions = extensions.map((extension) =>
        extension.kind === kind && extension.name === name
          ? { ...extension, enabled }
          : extension,
      );
      return fulfillJson(route, {
        extension: extensions.find(
          (extension) => extension.kind === kind && extension.name === name,
        ),
      });
    }

    return route.fallback();
  });

  return { enablementUpdates };
}

function fulfillJson(route: Route, body: unknown) {
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test.describe("Hackathon demo flow", () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page);
  });

  test("enables and disables registry capabilities from the config UI", async ({
    page,
  }) => {
    const registry = mockExtensionRegistryAPI(page);
    await page.goto("/workspace/extensions");

    await expect(
      page.getByRole("heading", { name: "Capability Configuration" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByRole("button", { name: /MCPs 0\/1/i }),
    ).toBeVisible();

    const localDocsRow = page
      .getByRole("listitem")
      .filter({ hasText: "Local Docs" });
    await expect(
      localDocsRow.getByText("Disabled", { exact: true }),
    ).toBeVisible();

    await localDocsRow
      .getByRole("switch", { name: "Enable Local Docs" })
      .click();
    await expect(
      localDocsRow.getByText("Enabled", { exact: true }),
    ).toBeVisible();
    await expect(
      localDocsRow.getByRole("switch", { name: "Disable Local Docs" }),
    ).toBeChecked();
    expect(registry.enablementUpdates).toContainEqual({
      kind: "mcp",
      name: "local-docs",
      enabled: true,
    });
    await expect(
      page.getByRole("button", { name: /MCPs 1\/1/i }),
    ).toBeVisible();

    await localDocsRow
      .getByRole("switch", { name: "Disable Local Docs" })
      .click();
    await expect(
      localDocsRow.getByText("Disabled", { exact: true }),
    ).toBeVisible();
    expect(registry.enablementUpdates).toContainEqual({
      kind: "mcp",
      name: "local-docs",
      enabled: false,
    });
    await expect(
      page.getByRole("button", { name: /MCPs 0\/1/i }),
    ).toBeVisible();
  });

  test("imports a registry extension and launches the chat demo prompt", async ({
    page,
  }) => {
    mockExtensionRegistryAPI(page);
    await page.goto("/workspace/extensions");

    await expect(
      page.getByRole("heading", { name: "Extension Registry" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Registry healthy")).toBeVisible();
    await expect(
      page.getByText("registries/demo_extensions.json").first(),
    ).toBeVisible();
    await expect(
      page
        .getByRole("listitem")
        .filter({ has: page.getByText("html-report", { exact: true }) }),
    ).toBeVisible();
    await expect(
      page
        .getByRole("listitem")
        .filter({ has: page.getByText("python-function", { exact: true }) }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Execution Audit" }),
    ).toBeVisible();
    const observability = page.locator("section").filter({
      has: page.getByRole("heading", { name: "Demo Observability" }),
    });
    await expect(observability.getByText("Needs Attention")).toBeVisible();
    await expect(observability.getByLabel("Active: 6")).toBeVisible();
    await expect(observability.getByLabel("Executions: 2")).toBeVisible();
    await expect(observability.getByLabel("Failures: 1")).toBeVisible();
    await expect(observability.getByLabel("Artifacts: 1")).toBeVisible();
    await expect(page.getByText("hackathon-readiness.html")).toBeVisible();
    await expect(page.getByText("Function not allowlisted")).toBeVisible();

    await page.getByRole("button", { name: /^Import$/ }).click();
    await expect(
      page.getByRole("heading", { name: "Import Extension Registry" }),
    ).toBeVisible();

    const registryJson = page.getByLabel("Registry JSON");
    await page.getByRole("button", { name: /Copy Sample/i }).click();
    await expect(registryJson).toHaveValue(/forecast-export/);

    await registryJson.fill(
      JSON.stringify({
        version: 1,
        extensions: [
          {
            kind: "tool",
            name: "forecast-export",
            enabled: true,
            source: "external://hackathon-forecast-registry",
            entrypoint: "internal_tools.forecast:export",
            description:
              "Exports a forecast table for the imported registry demo.",
            tags: ["forecast", "external"],
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
    await expect(
      page.getByText(
        "Imported registry source: external://hackathon-forecast-registry",
      ),
    ).toBeVisible();
    await expect(page.getByText("1 add")).toBeVisible();
    await expect(page.getByText("0 conflicts")).toBeVisible();

    await page.getByRole("button", { name: /Import Selected/i }).click();
    await expect(
      page.getByRole("heading", { name: "Import Extension Registry" }),
    ).toBeHidden();
    await expect(
      page.getByText("Forecast Export", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText(/from finance-demo/)).toBeVisible();
    await expect(page.getByText(/0123456789ab/)).toBeVisible();

    const forecastRow = page
      .getByRole("listitem")
      .filter({ has: page.getByText("forecast-export", { exact: true }) });
    await forecastRow.getByRole("button", { name: "Remove import" }).click();
    await expect(
      page.getByText("Forecast Export", { exact: true }),
    ).toBeHidden();

    await page.goto("/workspace/chats/new");

    const textarea = page.getByPlaceholder(/how can i assist you/i);
    await expect(textarea).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: /Capabilities/i }).click();
    await expect(
      page.getByText("Hackathon demo flow", { exact: true }),
    ).toBeVisible();
    await page.getByText("Hackathon demo flow", { exact: true }).click();

    await expect(textarea).toHaveValue(
      /Run the Brillio hackathon internal assistant demo end to end\./,
    );
    await expect(textarea).toHaveValue(/HTML Report/);
    await expect(textarea).toHaveValue(/CSV Export/);
    await expect(textarea).toHaveValue(/PDF Report/);
    await expect(textarea).toHaveValue(
      /internal_tools\.python_examples:summarize_metrics/,
    );
  });

  test("surfaces blocked registry import risk messaging", async ({ page }) => {
    mockExtensionRegistryAPI(page);
    await page.goto("/workspace/extensions");
    await expect(
      page.getByRole("heading", { name: "Extension Registry" }),
    ).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: /^Import$/ }).click();
    await page.getByLabel("Registry JSON").fill(
      JSON.stringify({
        version: 1,
        extensions: [
          {
            kind: "tool",
            name: "shell-tool",
            enabled: true,
            source: "registry",
            entrypoint: "os:system",
            risk_level: "high",
          },
        ],
      }),
    );
    await page.getByRole("button", { name: /Preview/i }).click();

    await expect(page.getByText("Shell Tool", { exact: true })).toBeVisible();
    await expect(page.getByText("1 external")).toBeVisible();
    await expect(page.getByText("1 high risk")).toBeVisible();
    await expect(page.getByText("1 blocked")).toBeVisible();
    await expect(
      page
        .getByLabel("Import Extension Registry")
        .getByText(
          "tool:shell-tool entrypoint 'os:system' is not allowed by DEERFLOW_EXTENSION_IMPORT_ENTRYPOINT_PREFIXES.",
        ),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Import Selected/i }),
    ).toBeDisabled();
  });

  test("requires approval before inserting high-risk chat capability", async ({
    page,
  }) => {
    mockExtensionRegistryAPI(page);
    await page.goto("/workspace/chats/new");

    const textarea = page.getByPlaceholder(/how can i assist you/i);
    await expect(textarea).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: /Capabilities/i }).click();
    await page.getByText("Python Function", { exact: true }).click();

    await expect(
      page.getByRole("heading", { name: "Approve high-risk capability" }),
    ).toBeVisible();
    await expect(page.getByText("Python Function").last()).toBeVisible();
    await expect(textarea).toHaveValue("");

    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(
      page.getByRole("heading", { name: "Approve high-risk capability" }),
    ).toBeHidden();
    await expect(textarea).toHaveValue("");

    await page.getByRole("button", { name: /Capabilities/i }).click();
    await page.getByText("Python Function", { exact: true }).click();
    await page.getByRole("button", { name: "Approve and insert" }).click();

    await expect(textarea).toHaveValue(/Use Python Function to /);
  });
});
