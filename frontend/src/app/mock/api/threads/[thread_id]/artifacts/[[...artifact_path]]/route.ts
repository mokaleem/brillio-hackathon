import fs from "fs";
import path from "path";

import type { NextRequest } from "next/server";

const DEMO_THREADS_ROOT = path.join(
  /*turbopackIgnore: true*/ process.cwd(),
  "public",
  "demo",
  "threads",
);

export async function GET(
  request: NextRequest,
  {
    params,
  }: {
    params: Promise<{
      thread_id: string;
      artifact_path?: string[] | undefined;
    }>;
  },
) {
  const threadId = (await params).thread_id;
  const artifactPath = (await params).artifact_path?.join("/") ?? "";
  if (artifactPath.startsWith("mnt/")) {
    const threadRoot = path.resolve(DEMO_THREADS_ROOT, threadId);
    const resolvedArtifactPath = path.resolve(
      threadRoot,
      artifactPath.replace(/^mnt\//, ""),
    );
    if (!resolvedArtifactPath.startsWith(`${threadRoot}${path.sep}`)) {
      return new Response("File not found", { status: 404 });
    }
    if (fs.existsSync(resolvedArtifactPath)) {
      if (request.nextUrl.searchParams.get("download") === "true") {
        // Attach the file to the response
        const headers = new Headers();
        headers.set(
          "Content-Disposition",
          `attachment; filename="${resolvedArtifactPath}"`,
        );
        return new Response(fs.readFileSync(resolvedArtifactPath), {
          status: 200,
          headers,
        });
      }
      if (resolvedArtifactPath.endsWith(".mp4")) {
        return new Response(fs.readFileSync(resolvedArtifactPath), {
          status: 200,
          headers: {
            "Content-Type": "video/mp4",
          },
        });
      }
      return new Response(fs.readFileSync(resolvedArtifactPath), {
        status: 200,
      });
    }
  }
  return new Response("File not found", { status: 404 });
}
