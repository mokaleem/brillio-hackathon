import { FilesIcon } from "lucide-react";
import { useMemo } from "react";

import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/workspace/tooltip";
import {
  formatArtifactSummary,
  summarizeArtifactFiles,
} from "@/core/artifacts/catalog";
import { useI18n } from "@/core/i18n/hooks";

import { useMaybeSidecar } from "../sidecar/context";

import { useArtifacts } from "./context";

export const ArtifactTrigger = () => {
  const { t } = useI18n();
  const { artifacts, setOpen: setArtifactsOpen } = useArtifacts();
  const sidecar = useMaybeSidecar();
  const summary = useMemo(
    () => summarizeArtifactFiles(artifacts ?? []),
    [artifacts],
  );

  if (!artifacts || artifacts.length === 0) {
    return null;
  }
  return (
    <Tooltip content={formatArtifactSummary(summary)}>
      <Button
        aria-label={t.common.showArtifacts}
        className="text-muted-foreground hover:text-foreground gap-1.5"
        variant="ghost"
        data-testid="artifact-trigger"
        onClick={() => {
          sidecar?.close();
          setArtifactsOpen(true);
        }}
      >
        <FilesIcon />
        <span className="hidden sm:inline">Artifact Center</span>
        <span className="inline sm:hidden">{t.common.artifacts}</span>
        <span className="bg-muted text-muted-foreground rounded px-1.5 font-mono text-[10px]">
          {summary.total}
        </span>
      </Button>
    </Tooltip>
  );
};
