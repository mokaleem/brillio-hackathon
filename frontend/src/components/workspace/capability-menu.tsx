"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BotIcon,
  FlaskConicalIcon,
  PackageOpenIcon,
  RefreshCcwIcon,
  ShieldAlertIcon,
  SparklesIcon,
  WrenchIcon,
} from "lucide-react";
import { useMemo, useState } from "react";

import {
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuItem,
  PromptInputActionMenuTrigger,
} from "@/components/ai-elements/prompt-input";
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
import {
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { loadExtensions } from "@/core/internal-registry/api";
import {
  buildDemoConversationPrompt,
  buildExtensionPrompt,
  extensionDisplayName,
  formatExtensionKind,
  requiresCapabilityApproval,
} from "@/core/internal-registry/browser";
import type {
  ExtensionDescriptor,
  ExtensionKind,
} from "@/core/internal-registry/types";
import { cn } from "@/lib/utils";

const CHAT_CAPABILITIES_QUERY_KEY = [
  "extensions",
  "chat-capabilities",
] as const;
const KIND_ORDER: ExtensionKind[] = ["agent", "tool", "skill", "mcp"];
const KIND_ICON: Record<ExtensionKind, typeof BotIcon> = {
  agent: BotIcon,
  mcp: PackageOpenIcon,
  tool: WrenchIcon,
  skill: SparklesIcon,
};

export function CapabilityMenu({
  disabled,
  onInsertPrompt,
}: {
  disabled?: boolean;
  onInsertPrompt: (prompt: string) => void;
}) {
  const [pendingApproval, setPendingApproval] =
    useState<ExtensionDescriptor | null>(null);
  const capabilitiesQuery = useQuery({
    queryKey: CHAT_CAPABILITIES_QUERY_KEY,
    queryFn: () => loadExtensions(),
    staleTime: 30_000,
  });

  const grouped = useMemo(() => {
    const groups: Record<ExtensionKind, ExtensionDescriptor[]> = {
      agent: [],
      mcp: [],
      skill: [],
      tool: [],
    };

    for (const extension of capabilitiesQuery.data?.extensions ?? []) {
      if (extension.enabled) {
        groups[extension.kind].push(extension);
      }
    }

    for (const kind of KIND_ORDER) {
      groups[kind].sort((a, b) =>
        extensionDisplayName(a).localeCompare(extensionDisplayName(b)),
      );
    }

    return groups;
  }, [capabilitiesQuery.data?.extensions]);

  const enabledCount = KIND_ORDER.reduce(
    (count, kind) => count + grouped[kind].length,
    0,
  );

  const insertCapability = (extension: ExtensionDescriptor) => {
    if (requiresCapabilityApproval(extension)) {
      setPendingApproval(extension);
      return;
    }
    onInsertPrompt(buildExtensionPrompt(extension));
  };

  const approvePendingCapability = () => {
    if (!pendingApproval) {
      return;
    }
    onInsertPrompt(buildExtensionPrompt(pendingApproval));
    setPendingApproval(null);
  };

  return (
    <>
      <PromptInputActionMenu>
        <PromptInputActionMenuTrigger
          className="max-w-36 gap-1! px-2!"
          disabled={disabled}
        >
          <PackageOpenIcon className="size-3" />
          <span className="hidden truncate text-xs font-normal sm:inline">
            Capabilities
          </span>
          {enabledCount > 0 && (
            <span className="text-muted-foreground font-mono text-[10px]">
              {enabledCount}
            </span>
          )}
        </PromptInputActionMenuTrigger>
        <PromptInputActionMenuContent className="w-88 max-w-[calc(100vw-2rem)]">
          <DropdownMenuGroup>
            <DropdownMenuLabel className="text-muted-foreground text-xs">
              Available capabilities
            </DropdownMenuLabel>

            {capabilitiesQuery.isLoading ? (
              <CapabilityStatus icon="loading" label="Loading registry" />
            ) : capabilitiesQuery.isError ? (
              <CapabilityStatus
                icon="error"
                label={
                  capabilitiesQuery.error instanceof Error
                    ? capabilitiesQuery.error.message
                    : "Registry unavailable"
                }
              />
            ) : enabledCount === 0 ? (
              <CapabilityStatus icon="empty" label="No enabled extensions" />
            ) : (
              <>
                <PromptInputActionMenuItem
                  onSelect={() =>
                    onInsertPrompt(
                      buildDemoConversationPrompt(
                        capabilitiesQuery.data?.extensions ?? [],
                      ),
                    )
                  }
                >
                  <div className="flex min-w-0 flex-1 items-start gap-2">
                    <div className="bg-muted mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md border">
                      <FlaskConicalIcon className="text-muted-foreground size-3.5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">
                        Hackathon demo flow
                      </div>
                      <div className="text-muted-foreground mt-0.5 line-clamp-2 text-xs">
                        Insert a ready-to-run prompt for registry discovery,
                        artifacts, and Python execution.
                      </div>
                    </div>
                  </div>
                </PromptInputActionMenuItem>
                {KIND_ORDER.map((kind) => {
                  const items = grouped[kind];
                  if (items.length === 0) {
                    return null;
                  }

                  return (
                    <div key={kind}>
                      <DropdownMenuSeparator />
                      <DropdownMenuLabel className="text-muted-foreground text-xs">
                        {formatExtensionKind(kind)}
                      </DropdownMenuLabel>
                      {items.slice(0, 6).map((extension) => (
                        <CapabilityItem
                          key={`${extension.kind}:${extension.name}`}
                          extension={extension}
                          onSelect={() => insertCapability(extension)}
                        />
                      ))}
                    </div>
                  );
                })}
              </>
            )}
          </DropdownMenuGroup>
        </PromptInputActionMenuContent>
      </PromptInputActionMenu>
      <CapabilityApprovalDialog
        extension={pendingApproval}
        onCancel={() => setPendingApproval(null)}
        onApprove={approvePendingCapability}
      />
    </>
  );
}

function CapabilityItem({
  extension,
  onSelect,
}: {
  extension: ExtensionDescriptor;
  onSelect: () => void;
}) {
  const Icon = KIND_ICON[extension.kind];
  return (
    <PromptInputActionMenuItem onSelect={onSelect}>
      <div className="flex min-w-0 flex-1 items-start gap-2">
        <div className="bg-muted mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md border">
          <Icon className="text-muted-foreground size-3.5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate text-sm font-medium">
              {extensionDisplayName(extension)}
            </span>
            {extension.risk_level && (
              <Badge variant="outline" className="h-5 px-1.5 text-[10px]">
                {extension.risk_level}
              </Badge>
            )}
            {requiresCapabilityApproval(extension) && (
              <Badge
                variant="secondary"
                className="h-5 gap-1 px-1.5 text-[10px]"
              >
                <ShieldAlertIcon className="size-3" />
                Approval
              </Badge>
            )}
          </div>
          <div className="text-muted-foreground mt-0.5 line-clamp-2 text-xs">
            {extension.description || extension.name}
          </div>
        </div>
      </div>
    </PromptInputActionMenuItem>
  );
}

function CapabilityApprovalDialog({
  extension,
  onCancel,
  onApprove,
}: {
  extension: ExtensionDescriptor | null;
  onCancel: () => void;
  onApprove: () => void;
}) {
  const label = extension ? extensionDisplayName(extension) : "capability";
  return (
    <Dialog open={!!extension} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldAlertIcon className="text-muted-foreground size-4" />
            Approve high-risk capability
          </DialogTitle>
          <DialogDescription>
            {label} is marked high risk. Confirm that you reviewed its source,
            owner, and runtime permissions before inserting this prompt.
          </DialogDescription>
        </DialogHeader>
        {extension && (
          <div className="bg-muted/40 rounded-md border px-3 py-2 text-sm">
            <div className="font-medium">{label}</div>
            <div className="text-muted-foreground mt-1 line-clamp-2 text-xs">
              {extension.description || extension.name}
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={onApprove}>Approve and insert</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CapabilityStatus({
  icon,
  label,
}: {
  icon: "loading" | "error" | "empty";
  label: string;
}) {
  return (
    <div className="text-muted-foreground flex items-center gap-2 px-2 py-3 text-sm">
      <RefreshCcwIcon
        className={cn("size-4", icon === "loading" && "animate-spin")}
      />
      <span className="truncate">{label}</span>
    </div>
  );
}
