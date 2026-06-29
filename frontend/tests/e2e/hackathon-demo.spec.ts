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

    if (request.method() === "POST" && pathname === "/api/extensions/reload") {
      return fulfillJson(route, {
        count: extensions.length,
        extensions,
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

test.describe("Hackathon demo flow", () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page);
    mockExtensionRegistryAPI(page);
  });

  test("imports a registry extension and launches the chat demo prompt", async ({
    page,
  }) => {
    await page.goto("/workspace/extensions");

    await expect(
      page.getByRole("heading", { name: "Extension Registry" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Registry healthy")).toBeVisible();
    await expect(
      page.getByText("registries/demo_extensions.json").first(),
    ).toBeVisible();
    await expect(page.getByText("HTML Report", { exact: true })).toBeVisible();
    await expect(
      page.getByText("Python Function", { exact: true }),
    ).toBeVisible();

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

    await page.getByRole("button", { name: /Import Selected/i }).click();
    await expect(
      page.getByRole("heading", { name: "Import Extension Registry" }),
    ).toBeHidden();
    await expect(
      page.getByText("Forecast Export", { exact: true }),
    ).toBeVisible();

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
