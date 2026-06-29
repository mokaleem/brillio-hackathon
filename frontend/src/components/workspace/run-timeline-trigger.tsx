"use client";

import {
  BotIcon,
  CheckCircle2Icon,
  Clock3Icon,
  PackageOpenIcon,
  RouteIcon,
  ShieldCheckIcon,
  WrenchIcon,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type {
  RunTimelineEvent,
  RunTimelineKind,
} from "@/core/threads/timeline";
import { cn } from "@/lib/utils";

const KIND_ICON: Record<RunTimelineKind, typeof RouteIcon> = {
  chain: RouteIcon,
  custom: PackageOpenIcon,
  audit: ShieldCheckIcon,
  model: BotIcon,
  run: Clock3Icon,
  tool: WrenchIcon,
};

export function RunTimelineTrigger({
  events,
  isStreaming,
}: {
  events: RunTimelineEvent[];
  isStreaming?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const recentEvents = useMemo(() => events.slice(-80).reverse(), [events]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="px-2 sm:px-3"
          aria-label="Open run timeline"
        >
          <RouteIcon className="size-4" />
          <span className="hidden sm:inline">Trace</span>
          {events.length > 0 && (
            <span className="text-muted-foreground font-mono text-[10px]">
              {events.length}
            </span>
          )}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[80dvh] max-w-2xl overflow-hidden p-0">
        <DialogHeader className="border-b px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <DialogTitle className="flex items-center gap-2 text-base">
              <RouteIcon className="size-4" />
              Run Timeline
            </DialogTitle>
            <Badge variant={isStreaming ? "default" : "secondary"}>
              {isStreaming ? "Streaming" : "Idle"}
            </Badge>
          </div>
        </DialogHeader>
        <div className="max-h-[62dvh] overflow-y-auto px-5 py-4">
          {recentEvents.length === 0 ? (
            <div className="flex min-h-48 flex-col items-center justify-center gap-2 rounded-lg border border-dashed text-center">
              <Clock3Icon className="text-muted-foreground size-7" />
              <div>
                <p className="text-sm font-medium">No run events yet</p>
                <p className="text-muted-foreground mt-1 max-w-sm text-xs">
                  Send a message to see model, tool, and orchestration activity.
                </p>
              </div>
            </div>
          ) : (
            <ol className="before:bg-border relative space-y-3 before:absolute before:top-2 before:bottom-2 before:left-4 before:w-px">
              {recentEvents.map((event) => (
                <TimelineRow key={event.id} event={event} />
              ))}
            </ol>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function TimelineRow({ event }: { event: RunTimelineEvent }) {
  const Icon = KIND_ICON[event.kind];
  return (
    <li className="relative flex gap-3 pl-10">
      <div className="bg-background absolute left-0 flex size-8 items-center justify-center rounded-md border">
        <Icon className="text-muted-foreground size-4" />
      </div>
      <div className="min-w-0 flex-1 rounded-md border px-3 py-2">
        <div className="flex min-w-0 items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate text-sm font-medium">{event.label}</div>
            <div className="text-muted-foreground truncate font-mono text-[11px]">
              {event.name}
            </div>
          </div>
          <Badge
            variant="outline"
            className={cn(
              "shrink-0 capitalize",
              event.phase === "end" && "border-emerald-500/30 text-emerald-700",
              event.phase === "error" &&
                "border-destructive/30 text-destructive",
            )}
          >
            {event.phase === "end" && <CheckCircle2Icon className="size-3" />}
            {event.phase}
          </Badge>
        </div>
        {event.summary && (
          <p className="text-muted-foreground mt-2 line-clamp-2 text-xs">
            {event.summary}
          </p>
        )}
      </div>
    </li>
  );
}
