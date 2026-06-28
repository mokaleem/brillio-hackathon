"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BotIcon,
  CheckCircle2Icon,
  Code2Icon,
  FileTextIcon,
  PackageOpenIcon,
  RefreshCcwIcon,
  SearchIcon,
  ShieldAlertIcon,
  SparklesIcon,
  WrenchIcon,
  XCircleIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import {
  loadExtensions,
  reloadExtensions,
  updateExtensionEnabled,
  validateExtensions,
} from "@/core/extensions/api";
import {
  applyExtensionEnabledUpdate,
  filterExtensions,
  formatExtensionKind,
  summarizeExtensions,
  type ExtensionKindFilter,
  type ExtensionStatusFilter,
} from "@/core/extensions/browser";
import type {
  ExtensionDescriptor,
  ExtensionKind,
  ExtensionsResponse,
} from "@/core/extensions/types";
import { cn } from "@/lib/utils";

const EXTENSION_QUERY_KEY = ["extensions", "catalog"] as const;
const EMPTY_EXTENSIONS: ExtensionDescriptor[] = [];

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
  const [pendingToggle, setPendingToggle] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const extensionsQuery = useQuery({
    queryKey: EXTENSION_QUERY_KEY,
    queryFn: () => loadExtensions(),
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
      toast.success("Extension registry reloaded");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : String(error));
    },
  });

  const validateMutation = useMutation({
    mutationFn: validateExtensions,
    onSuccess: (result) => {
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

      <section className="grid gap-3 border-b px-6 py-4 sm:grid-cols-2 lg:grid-cols-5">
        <SummaryMetric label="Total" value={summary.total} />
        <SummaryMetric label="Enabled" value={summary.enabled} />
        <SummaryMetric label="Disabled" value={summary.disabled} />
        <SummaryMetric label="Tools" value={summary.byKind.tool} />
        <SummaryMetric label="Skills" value={summary.byKind.skill} />
      </section>

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
