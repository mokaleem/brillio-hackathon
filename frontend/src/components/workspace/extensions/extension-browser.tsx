"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BotIcon,
  CheckCircle2Icon,
  Code2Icon,
  CopyIcon,
  FileTextIcon,
  FileJsonIcon,
  PackageOpenIcon,
  RefreshCcwIcon,
  SearchIcon,
  ShieldAlertIcon,
  SparklesIcon,
  UploadIcon,
  WrenchIcon,
  XCircleIcon,
} from "lucide-react";
import { useEffect, useMemo, useState, type ChangeEvent } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  commitExtensionImport,
  loadExtensionHealth,
  loadExtensions,
  previewExtensionImport,
  reloadExtensions,
  updateExtensionEnabled,
  validateExtensions,
} from "@/core/extensions/api";
import {
  applyExtensionEnabledUpdate,
  filterExtensions,
  formatExtensionKind,
  getExtensionExamplePrompts,
  getExtensionPromptTemplate,
  summarizeExtensions,
  type ExtensionKindFilter,
  type ExtensionStatusFilter,
} from "@/core/extensions/browser";
import type {
  ExtensionDescriptor,
  ExtensionHealthResponse,
  ExtensionImportPreviewResponse,
  ExtensionKind,
  ExtensionsResponse,
} from "@/core/extensions/types";
import { cn } from "@/lib/utils";

const EXTENSION_QUERY_KEY = ["extensions", "catalog"] as const;
const EXTENSION_HEALTH_QUERY_KEY = ["extensions", "health"] as const;
const EMPTY_EXTENSIONS: ExtensionDescriptor[] = [];
const IMPORT_MANIFEST_MAX_BYTES = 512 * 1024;
const SAMPLE_REGISTRY_JSON = JSON.stringify(
  {
    version: 1,
    metadata: {
      registry: "finance-demo",
      reviewed_by: "platform",
    },
    extensions: [
      {
        kind: "tool",
        name: "forecast-export",
        enabled: false,
        source: "registry",
        entrypoint: "company_tools.forecast:export",
        description: "Export forecast rows to a reviewed CSV format",
        tags: ["finance", "artifact"],
        risk_level: "medium",
        display_name: "Forecast Export",
        metadata: {
          prompt_template: "Use {{display_name}} to export forecast rows for ",
          input_schema: {
            rows_json: "JSON array of forecast rows",
          },
        },
      },
    ],
  },
  null,
  2,
);

const kindOptions: { value: ExtensionKindFilter; label: string }[] = [
  { value: "all", label: "All types" },
  { value: "agent", label: "Agents" },
  { value: "mcp", label: "MCPs" },
  { value: "tool", label: "Tools" },
  { value: "skill", label: "Skills" },
];

const statusOptions: { value: ExtensionStatusFilter; label: string }[] = [
  { value: "all", label: "All states" },
  { value: "enabled", label: "Enabled" },
  { value: "disabled", label: "Disabled" },
];

const kindIcon: Record<ExtensionKind, typeof BotIcon> = {
  agent: BotIcon,
  mcp: PackageOpenIcon,
  tool: WrenchIcon,
  skill: SparklesIcon,
};

export function ExtensionBrowser() {
  const [kind, setKind] = useState<ExtensionKindFilter>("all");
  const [status, setStatus] = useState<ExtensionStatusFilter>("all");
  const [query, setQuery] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [pendingToggle, setPendingToggle] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const extensionsQuery = useQuery({
    queryKey: EXTENSION_QUERY_KEY,
    queryFn: () => loadExtensions(),
  });
  const healthQuery = useQuery({
    queryKey: EXTENSION_HEALTH_QUERY_KEY,
    queryFn: () => loadExtensionHealth(),
  });

  const extensions = extensionsQuery.data?.extensions ?? EMPTY_EXTENSIONS;
  const summary = useMemo(() => summarizeExtensions(extensions), [extensions]);
  const visibleExtensions = useMemo(
    () => filterExtensions(extensions, { kind, status, query }),
    [extensions, kind, query, status],
  );

  const reloadMutation = useMutation({
    mutationFn: () => reloadExtensions(kind === "all" ? undefined : { kind }),
    onSuccess: (data) => {
      queryClient.setQueryData<ExtensionsResponse>(EXTENSION_QUERY_KEY, data);
      void queryClient.invalidateQueries({
        queryKey: EXTENSION_HEALTH_QUERY_KEY,
      });
      toast.success("Extension registry reloaded");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : String(error));
    },
  });

  const validateMutation = useMutation({
    mutationFn: validateExtensions,
    onSuccess: (result) => {
      void queryClient.invalidateQueries({
        queryKey: EXTENSION_HEALTH_QUERY_KEY,
      });
      if (result.valid) {
        toast.success(`Registry is valid (${result.count} entries)`);
      } else {
        toast.error(result.errors[0] ?? "Registry validation failed");
      }
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : String(error));
    },
  });

  const toggleMutation = useMutation({
    mutationFn: async (extension: ExtensionDescriptor) => {
      setPendingToggle(extensionKey(extension));
      return updateExtensionEnabled(
        extension.kind,
        extension.name,
        !extension.enabled,
      );
    },
    onSuccess: ({ extension }) => {
      queryClient.setQueryData<ExtensionsResponse>(
        EXTENSION_QUERY_KEY,
        (current) => ({
          count: current?.count ?? extensions.length,
          extensions: applyExtensionEnabledUpdate(
            current?.extensions ?? extensions,
            extension,
          ),
        }),
      );
      toast.success(
        `${extension.display_name ?? extension.name} ${
          extension.enabled ? "enabled" : "disabled"
        }`,
      );
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : String(error));
    },
    onSettled: () => setPendingToggle(null),
  });

  return (
    <div className="flex size-full min-h-0 flex-col">
      <header className="flex flex-col gap-4 border-b px-6 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <PackageOpenIcon className="text-muted-foreground size-5" />
            <h1 className="text-xl font-semibold">Extension Registry</h1>
          </div>
          <p className="text-muted-foreground mt-1 text-sm">
            Browse agents, MCPs, tools, and skills loaded from local manifests
            or external registries.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            <UploadIcon className="size-4" />
            Import
          </Button>
          <Button
            variant="outline"
            onClick={() => validateMutation.mutate()}
            disabled={validateMutation.isPending}
          >
            <CheckCircle2Icon className="size-4" />
            Validate
          </Button>
          <Button
            onClick={() => reloadMutation.mutate()}
            disabled={reloadMutation.isPending}
          >
            <RefreshCcwIcon
              className={cn(
                "size-4",
                reloadMutation.isPending && "animate-spin",
              )}
            />
            Reload
          </Button>
        </div>
      </header>
      <ExtensionImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        onImported={(data) => {
          queryClient.setQueryData<ExtensionsResponse>(
            EXTENSION_QUERY_KEY,
            data,
          );
          void queryClient.invalidateQueries({
            queryKey: EXTENSION_HEALTH_QUERY_KEY,
          });
          toast.success("Imported selected extensions");
        }}
      />

      <section className="grid gap-3 border-b px-6 py-4 sm:grid-cols-2 lg:grid-cols-5">
        <SummaryMetric label="Total" value={summary.total} />
        <SummaryMetric label="Enabled" value={summary.enabled} />
        <SummaryMetric label="Disabled" value={summary.disabled} />
        <SummaryMetric label="Tools" value={summary.byKind.tool} />
        <SummaryMetric label="Skills" value={summary.byKind.skill} />
      </section>

      <ExtensionHealthPanel
        health={healthQuery.data}
        isLoading={healthQuery.isLoading}
        error={
          healthQuery.error instanceof Error ? healthQuery.error.message : null
        }
        onRetry={() => void healthQuery.refetch()}
      />

      <section className="flex flex-col gap-3 border-b px-6 py-4 lg:flex-row lg:items-center">
        <label className="relative min-w-0 flex-1">
          <span className="sr-only">Search extensions</span>
          <SearchIcon className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by name, source, tag, owner, or requirement"
            className="pl-9"
          />
        </label>
        <div className="grid grid-cols-2 gap-2 sm:flex">
          <Select
            value={kind}
            onValueChange={(value) => setKind(value as ExtensionKindFilter)}
          >
            <SelectTrigger className="w-full sm:w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {kindOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={status}
            onValueChange={(value) => setStatus(value as ExtensionStatusFilter)}
          >
            <SelectTrigger className="w-full sm:w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {statusOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </section>

      <main className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        {extensionsQuery.isLoading ? (
          <ExtensionBrowserSkeleton />
        ) : extensionsQuery.isError ? (
          <ExtensionBrowserError
            message={
              extensionsQuery.error instanceof Error
                ? extensionsQuery.error.message
                : "Could not load the extension registry."
            }
            onRetry={() => void extensionsQuery.refetch()}
          />
        ) : visibleExtensions.length === 0 ? (
          <ExtensionBrowserEmpty />
        ) : (
          <div className="overflow-hidden rounded-lg border">
            <div className="bg-muted/50 text-muted-foreground hidden grid-cols-[minmax(220px,1.4fr)_110px_minmax(180px,1fr)_110px_96px] gap-4 border-b px-4 py-2 text-xs font-medium lg:grid">
              <span>Extension</span>
              <span>Type</span>
              <span>Source</span>
              <span>Risk</span>
              <span className="text-right">Enabled</span>
            </div>
            <ul className="divide-y">
              {visibleExtensions.map((extension) => (
                <ExtensionRow
                  key={extensionKey(extension)}
                  extension={extension}
                  pending={pendingToggle === extensionKey(extension)}
                  onToggle={() => toggleMutation.mutate(extension)}
                />
              ))}
            </ul>
          </div>
        )}
      </main>
    </div>
  );
}

function SummaryMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border px-4 py-3">
      <div className="text-muted-foreground text-xs font-medium">{label}</div>
      <div className="mt-1 font-mono text-2xl leading-none font-semibold">
        {value}
      </div>
    </div>
  );
}

function ExtensionImportDialog({
  open,
  onOpenChange,
  onImported,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: (data: ExtensionsResponse) => void;
}) {
  const [manifestJson, setManifestJson] = useState("");
  const [registryUrl, setRegistryUrl] = useState("");
  const [preview, setPreview] = useState<ExtensionImportPreviewResponse | null>(
    null,
  );
  const [selected, setSelected] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!open) {
      setPreview(null);
      setSelected({});
      setRegistryUrl("");
    }
  }, [open]);

  const previewMutation = useMutation({
    mutationFn: previewExtensionImport,
    onSuccess: (result) => {
      setPreview(result);
      setSelected(
        Object.fromEntries(
          result.extensions
            .filter(
              (extension) =>
                !result.duplicates.includes(extensionKey(extension)),
            )
            .map((extension) => [extensionKey(extension), true]),
        ),
      );
      if (result.errors.length > 0) {
        toast.error(result.errors[0]);
      } else if (result.duplicates.length > 0) {
        toast.warning("Preview contains duplicate extension names");
      } else {
        toast.success(`Previewed ${result.count} extension entries`);
      }
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : String(error));
    },
  });

  const importMutation = useMutation({
    mutationFn: (keys: string[]) => commitExtensionImport(manifestJson, keys),
    onSuccess: (data) => {
      onImported(data);
      onOpenChange(false);
      setManifestJson("");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : String(error));
    },
  });

  const selectedKeys = useMemo(
    () =>
      Object.entries(selected)
        .filter(([, enabled]) => enabled)
        .map(([key]) => key),
    [selected],
  );

  const setImportJson = (json: string) => {
    setManifestJson(json);
    setPreview(null);
  };

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }
    if (file.size > IMPORT_MANIFEST_MAX_BYTES) {
      toast.error(formatImportSizeError(file.size));
      return;
    }
    setImportJson(await file.text());
  };

  const handleFetchUrl = async () => {
    if (!registryUrl.trim()) {
      return;
    }
    try {
      const response = await globalThis.fetch(registryUrl.trim());
      if (!response.ok) {
        throw new Error(`Registry URL returned ${response.status}`);
      }
      const contentLength = response.headers.get("content-length");
      if (contentLength && Number(contentLength) > IMPORT_MANIFEST_MAX_BYTES) {
        throw new Error(formatImportSizeError(Number(contentLength)));
      }
      const text = await response.text();
      const size = getImportManifestByteLength(text);
      if (size > IMPORT_MANIFEST_MAX_BYTES) {
        throw new Error(formatImportSizeError(size));
      }
      setImportJson(text);
      toast.success("Registry JSON loaded");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  };

  const handlePreview = () => {
    const size = getImportManifestByteLength(manifestJson);
    if (size > IMPORT_MANIFEST_MAX_BYTES) {
      toast.error(formatImportSizeError(size));
      return;
    }
    previewMutation.mutate(manifestJson);
  };

  const handleCopySample = async () => {
    setImportJson(SAMPLE_REGISTRY_JSON);
    try {
      await navigator.clipboard.writeText(SAMPLE_REGISTRY_JSON);
      toast.success("Sample registry JSON copied");
    } catch {
      toast.success("Sample registry JSON loaded");
    }
  };

  const canImport =
    Boolean(preview) &&
    (preview?.errors.length ?? 0) === 0 &&
    selectedKeys.length > 0 &&
    !importMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85dvh] max-w-3xl overflow-hidden p-0">
        <DialogHeader className="border-b px-5 py-4">
          <DialogTitle className="flex items-center gap-2 text-base">
            <FileJsonIcon className="size-4" />
            Import Extension Registry
          </DialogTitle>
          <DialogDescription>
            Load a registry JSON file, preview descriptors, then import selected
            capabilities into the local generated registry.
          </DialogDescription>
        </DialogHeader>
        <div className="min-h-0 overflow-y-auto px-5 py-4">
          <div className="grid gap-4">
            <div className="grid gap-2">
              <label className="text-sm font-medium" htmlFor="registry-url">
                Registry URL
              </label>
              <div className="flex gap-2">
                <Input
                  id="registry-url"
                  value={registryUrl}
                  onChange={(event) => setRegistryUrl(event.target.value)}
                  placeholder="https://example.com/extensions.json"
                />
                <Button
                  variant="outline"
                  onClick={() => void handleFetchUrl()}
                  disabled={!registryUrl.trim()}
                >
                  Fetch
                </Button>
              </div>
            </div>
            <div className="grid gap-2">
              <label className="text-sm font-medium" htmlFor="registry-json">
                Registry JSON
              </label>
              <Textarea
                id="registry-json"
                value={manifestJson}
                onChange={(event) => setImportJson(event.target.value)}
                className="min-h-48 font-mono text-xs"
                placeholder='{"version":1,"extensions":[]}'
              />
              <div className="flex flex-wrap gap-2">
                <Button asChild variant="outline" size="sm">
                  <label>
                    <UploadIcon className="size-4" />
                    Upload JSON
                    <input
                      className="sr-only"
                      type="file"
                      accept="application/json,.json"
                      onChange={(event) => void handleFileChange(event)}
                    />
                  </label>
                </Button>
                <Button variant="outline" size="sm" onClick={handleCopySample}>
                  <CopyIcon className="size-4" />
                  Copy Sample
                </Button>
                <Button
                  size="sm"
                  onClick={handlePreview}
                  disabled={!manifestJson.trim() || previewMutation.isPending}
                >
                  <CheckCircle2Icon className="size-4" />
                  Preview
                </Button>
              </div>
            </div>

            {preview && (
              <div className="rounded-lg border">
                <div className="bg-muted/50 flex flex-wrap items-center gap-2 border-b px-3 py-2">
                  <Badge
                    variant={preview.errors.length ? "destructive" : "outline"}
                  >
                    {preview.count} entries
                  </Badge>
                  {preview.duplicates.length > 0 && (
                    <Badge variant="secondary">
                      {preview.duplicates.length} duplicates
                    </Badge>
                  )}
                  <ImportReviewBadges preview={preview} />
                </div>
                {preview.errors.length > 0 || preview.warnings.length > 0 ? (
                  <div className="grid gap-2 border-b px-3 py-3 text-xs">
                    {preview.errors.map((message) => (
                      <HealthMessage
                        key={message}
                        tone="error"
                        message={message}
                      />
                    ))}
                    {preview.warnings.map((message) => (
                      <HealthMessage
                        key={message}
                        tone="warning"
                        message={message}
                      />
                    ))}
                  </div>
                ) : null}
                <ul className="max-h-64 divide-y overflow-y-auto">
                  {preview.extensions.map((extension) => {
                    const key = extensionKey(extension);
                    const duplicate = preview.duplicates.includes(key);
                    const blocked = hasIssueForExtension(preview.errors, key);
                    return (
                      <li
                        key={key}
                        className="grid gap-3 px-3 py-3 sm:grid-cols-[1fr_auto] sm:items-center"
                      >
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium">
                            {extension.display_name ?? extension.name}
                          </div>
                          <div className="text-muted-foreground mt-1 flex flex-wrap gap-2 text-xs">
                            <span>{formatExtensionKind(extension.kind)}</span>
                            <span className="font-mono">{extension.name}</span>
                            <RiskBadge riskLevel={extension.risk_level} />
                            {isExternalSource(extension) && (
                              <Badge variant="secondary">External</Badge>
                            )}
                            {blocked && (
                              <Badge variant="destructive">
                                <ShieldAlertIcon className="size-3" />
                                Blocked
                              </Badge>
                            )}
                            {duplicate && <span>Already configured</span>}
                          </div>
                        </div>
                        <Switch
                          checked={selected[key] ?? false}
                          disabled={duplicate}
                          onCheckedChange={(enabled) =>
                            setSelected((current) => ({
                              ...current,
                              [key]: enabled,
                            }))
                          }
                          aria-label={`Import ${extension.name}`}
                        />
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>
        </div>
        <DialogFooter className="border-t px-5 py-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            disabled={!canImport}
            onClick={() => importMutation.mutate(selectedKeys)}
          >
            Import Selected
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ImportReviewBadges({
  preview,
}: {
  preview: ExtensionImportPreviewResponse;
}) {
  const externalCount = preview.extensions.filter(isExternalSource).length;
  const highRiskCount = preview.extensions.filter(
    (extension) => extension.risk_level === "high",
  ).length;
  const blockedCount = collectIssueKeys(preview.errors).size;
  const warningCount = preview.warnings.length;

  return (
    <>
      {externalCount > 0 && (
        <Badge variant="secondary">{externalCount} external</Badge>
      )}
      {highRiskCount > 0 && (
        <Badge variant="destructive">
          <ShieldAlertIcon className="size-3" />
          {highRiskCount} high risk
        </Badge>
      )}
      {blockedCount > 0 && (
        <Badge variant="destructive">
          <ShieldAlertIcon className="size-3" />
          {blockedCount} blocked
        </Badge>
      )}
      {warningCount > 0 && (
        <Badge variant="secondary">{warningCount} warnings</Badge>
      )}
    </>
  );
}

function ExtensionHealthPanel({
  health,
  isLoading,
  error,
  onRetry,
}: {
  health: ExtensionHealthResponse | undefined;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  if (isLoading) {
    return (
      <section className="border-b px-6 py-3">
        <div className="flex items-center gap-3 rounded-lg border px-4 py-3">
          <RefreshCcwIcon className="text-muted-foreground size-4 animate-spin" />
          <span className="text-muted-foreground text-sm">
            Checking registry health
          </span>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="border-b px-6 py-3">
        <div className="flex flex-col gap-3 rounded-lg border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-medium">
              <XCircleIcon className="text-destructive size-4" />
              Registry health unavailable
            </div>
            <p className="text-muted-foreground mt-1 truncate text-sm">
              {error}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCcwIcon className="size-4" />
            Retry
          </Button>
        </div>
      </section>
    );
  }

  if (!health) {
    return null;
  }

  const statusLabel = health.valid ? "Registry healthy" : "Registry invalid";
  const issueCount = health.errors.length + health.warnings.length;

  return (
    <section className="border-b px-6 py-3">
      <div className="rounded-lg border px-4 py-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              {health.valid ? (
                <CheckCircle2Icon className="size-4 text-emerald-600" />
              ) : (
                <XCircleIcon className="text-destructive size-4" />
              )}
              <span className="text-sm font-medium">{statusLabel}</span>
              <Badge variant="outline">{health.count} entries</Badge>
              {issueCount > 0 && (
                <Badge
                  variant={
                    health.errors.length > 0 ? "destructive" : "secondary"
                  }
                >
                  {issueCount} issue{issueCount === 1 ? "" : "s"}
                </Badge>
              )}
            </div>
            <div className="text-muted-foreground mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
              {health.manifests.length > 0 ? (
                health.manifests.map((manifest) => (
                  <span
                    key={manifest}
                    className="max-w-full truncate font-mono"
                  >
                    {manifest}
                  </span>
                ))
              ) : (
                <span>No registry manifests configured</span>
              )}
            </div>
          </div>
          <div className="grid gap-2 text-xs lg:min-w-80">
            {health.errors.slice(0, 2).map((message) => (
              <HealthMessage key={message} tone="error" message={message} />
            ))}
            {health.warnings.slice(0, 2).map((message) => (
              <HealthMessage key={message} tone="warning" message={message} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function HealthMessage({
  tone,
  message,
}: {
  tone: "error" | "warning";
  message: string;
}) {
  return (
    <div className="text-muted-foreground flex min-w-0 items-start gap-2">
      <ShieldAlertIcon
        className={cn(
          "mt-0.5 size-3.5 shrink-0",
          tone === "error" ? "text-destructive" : "text-amber-600",
        )}
      />
      <span className="line-clamp-2">{message}</span>
    </div>
  );
}

function ExtensionRow({
  extension,
  pending,
  onToggle,
}: {
  extension: ExtensionDescriptor;
  pending: boolean;
  onToggle: () => void;
}) {
  const Icon = kindIcon[extension.kind];
  const title = extension.display_name ?? extension.name;
  const promptTemplate = getExtensionPromptTemplate(extension);
  const examplePrompts = getExtensionExamplePrompts(extension);
  const hasPromptMetadata =
    promptTemplate !== null || examplePrompts.length > 0;
  return (
    <li className="grid gap-3 px-4 py-4 lg:grid-cols-[minmax(220px,1.4fr)_110px_minmax(180px,1fr)_110px_96px] lg:items-center">
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-3">
          <div className="bg-muted flex size-9 shrink-0 items-center justify-center rounded-md border">
            <Icon className="text-muted-foreground size-4" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-medium">{title}</div>
            <div className="text-muted-foreground truncate font-mono text-xs">
              {extension.name}
            </div>
          </div>
        </div>
        {extension.description && (
          <p className="text-muted-foreground mt-2 line-clamp-2 text-sm lg:max-w-xl">
            {extension.description}
          </p>
        )}
        {extension.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {extension.tags.slice(0, 4).map((tag) => (
              <Badge key={tag} variant="secondary">
                {tag}
              </Badge>
            ))}
          </div>
        )}
        {hasPromptMetadata && (
          <div className="bg-muted/40 text-muted-foreground mt-3 space-y-1 rounded-md border px-3 py-2 text-xs">
            {promptTemplate && (
              <div className="min-w-0">
                <span className="text-foreground font-medium">
                  Prompt template:
                </span>{" "}
                <span className="font-mono break-words">{promptTemplate}</span>
              </div>
            )}
            {examplePrompts.length > 0 && (
              <div className="min-w-0">
                <span className="text-foreground font-medium">
                  Example prompt:
                </span>{" "}
                <span className="break-words">{examplePrompts[0]}</span>
              </div>
            )}
          </div>
        )}
      </div>

      <div>
        <Badge variant="outline">{formatExtensionKind(extension.kind)}</Badge>
      </div>

      <div className="min-w-0 text-sm">
        <div className="flex min-w-0 items-center gap-2">
          <Code2Icon className="text-muted-foreground size-4 shrink-0" />
          <span className="truncate">{extension.source}</span>
        </div>
        {extension.entrypoint && (
          <div className="text-muted-foreground mt-1 truncate font-mono text-xs">
            {extension.entrypoint}
          </div>
        )}
        {extension.requires.length > 0 && (
          <div className="text-muted-foreground mt-1 flex min-w-0 items-center gap-1 text-xs">
            <FileTextIcon className="size-3.5 shrink-0" />
            <span className="truncate">
              Requires {extension.requires.join(", ")}
            </span>
          </div>
        )}
      </div>

      <div>
        <RiskBadge riskLevel={extension.risk_level} />
      </div>

      <div className="flex items-center justify-between gap-3 lg:justify-end">
        <span className="text-muted-foreground text-sm lg:hidden">Enabled</span>
        <Switch
          checked={extension.enabled}
          disabled={pending}
          onCheckedChange={onToggle}
          aria-label={`${extension.enabled ? "Disable" : "Enable"} ${title}`}
        />
      </div>
    </li>
  );
}

function RiskBadge({
  riskLevel,
}: {
  riskLevel: ExtensionDescriptor["risk_level"];
}) {
  if (!riskLevel) {
    return <Badge variant="secondary">Unspecified</Badge>;
  }

  const destructive = riskLevel === "high";
  return (
    <Badge variant={destructive ? "destructive" : "outline"}>
      {destructive ? <ShieldAlertIcon className="size-3" /> : null}
      {riskLevel}
    </Badge>
  );
}

function ExtensionBrowserSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading extensions">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="rounded-lg border p-4">
          <div className="flex items-center gap-3">
            <Skeleton className="size-9" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-4 w-56 max-w-full" />
              <Skeleton className="h-3 w-36 max-w-full" />
            </div>
            <Skeleton className="h-5 w-12" />
          </div>
        </div>
      ))}
    </div>
  );
}

function ExtensionBrowserError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center gap-3 rounded-lg border border-dashed text-center">
      <XCircleIcon className="text-destructive size-8" />
      <div>
        <p className="font-medium">Registry unavailable</p>
        <p className="text-muted-foreground mt-1 max-w-md text-sm">{message}</p>
      </div>
      <Button variant="outline" onClick={onRetry}>
        <RefreshCcwIcon className="size-4" />
        Retry
      </Button>
    </div>
  );
}

function ExtensionBrowserEmpty() {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center gap-3 rounded-lg border border-dashed text-center">
      <PackageOpenIcon className="text-muted-foreground size-8" />
      <div>
        <p className="font-medium">No extensions found</p>
        <p className="text-muted-foreground mt-1 max-w-md text-sm">
          Adjust the filters or add descriptors to a configured registry
          manifest.
        </p>
      </div>
    </div>
  );
}

function extensionKey(extension: ExtensionDescriptor) {
  return `${extension.kind}:${extension.name}`;
}

function isExternalSource(extension: ExtensionDescriptor) {
  return extension.source !== "local";
}

function hasIssueForExtension(messages: string[], key: string) {
  return collectIssueKeys(messages).has(key);
}

function collectIssueKeys(messages: string[]) {
  const keys = new Set<string>();
  for (const message of messages) {
    const matches = message.matchAll(/\b(agent|mcp|tool|skill):[a-z0-9-]+\b/g);
    for (const match of matches) {
      keys.add(match[0]);
    }
  }
  return keys;
}

function getImportManifestByteLength(value: string) {
  return new TextEncoder().encode(value).length;
}

function formatImportSizeError(size: number) {
  return `Registry JSON is too large (${formatBytes(size)}). Limit is ${formatBytes(
    IMPORT_MANIFEST_MAX_BYTES,
  )}.`;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KiB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}
