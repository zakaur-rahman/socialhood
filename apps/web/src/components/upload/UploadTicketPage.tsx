"use client";

import { useRef, useState } from "react";

import { PageFrame } from "@/components/shell/PageFrame";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompleteMcpUpload, useMcpUpload } from "@/lib/api/queries";
import { extensionOf, resourceTypeFor, sendToStorage } from "@/lib/media/upload";
import { useCurrentWorkspace } from "@/lib/workspace";

const MB = 1024 * 1024;

/** ["mp4", "mov"] → "an MP4 or MOV" (the article follows the first format's sound). */
function formatList(formats: string[]): string {
  const names = formats.map((f) => f.toUpperCase());
  const list = names.length > 1 ? `${names.slice(0, -1).join(", ")} or ${names.at(-1)}` : (names[0] ?? "");
  return `${/^[AEFHILMNORSX]/.test(list) ? "an" : "a"} ${list}`;
}

/**
 * C-165: an AI app that cannot run an upload command gives the member this page's link. The file
 * goes straight to storage with the ticket's signature (it never passes through our servers), then
 * the page tells the API, which adds it to the media library. The AI app finds it with its next
 * check. The page keeps to the ticket's kind and limits, which the API enforces again.
 */
export function UploadTicketPage({ ticketId }: { ticketId: string }) {
  const wid = useCurrentWorkspace().id;
  const ticket = useMcpUpload(wid, ticketId);
  const complete = useCompleteMcpUpload(wid, ticketId);
  const input = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const data = ticket.data;
  const kind = data?.kind;
  const limits = data?.limits as { formats?: string[]; max_mb?: number } | undefined;
  const accept = (limits?.formats ?? []).map((f) => `.${f}`).join(",");

  async function send(file: File) {
    if (!data?.upload || !kind) return;
    setProblem(null);
    if (limits?.formats && !limits.formats.includes(extensionOf(file.name))) {
      setProblem(`Use ${formatList(limits.formats)} file.`);
      return;
    }
    if (resourceTypeFor(file) !== kind) {
      setProblem(kind === "image" ? "This upload is for an image." : "This upload is for a video.");
      return;
    }
    if (limits?.max_mb && file.size > limits.max_mb * MB) {
      setProblem(`Files can be up to ${limits.max_mb} MB here.`);
      return;
    }
    try {
      setProgress(0);
      const { public_id } = await sendToStorage(data.upload, file, { onProgress: setProgress });
      await complete.mutateAsync(public_id);
    } catch (error) {
      setProblem(error instanceof Error ? error.message : "The upload didn't finish. Try again.");
    } finally {
      setProgress(null);
    }
  }

  let body;
  if (ticket.isPending) {
    body = <Skeleton className="h-32 w-full" role="status" aria-busy="true" aria-label="Loading the upload" />;
  } else if (ticket.isError) {
    body = <ErrorState error={ticket.error} onRetry={() => void ticket.refetch()} />;
  } else if (data?.status === "uploaded") {
    body = (
      <Card padding="roomy" className="space-y-1" role="status">
        <p className="font-medium text-fg">The file is in your media library.</p>
        <p className="text-sm text-fg-secondary">Go back to your AI app. It can use the file now.</p>
      </Card>
    );
  } else if (data?.status === "rejected") {
    body = (
      <Card padding="roomy" className="space-y-1" role="alert">
        <p className="font-medium text-fg">The file was rejected.</p>
        <p className="text-sm text-fg-secondary">
          {data.reason ?? "It broke one of the limits."} Ask your AI app for a new upload.
        </p>
      </Card>
    );
  } else if (data?.status === "expired") {
    body = (
      <Card padding="roomy" className="space-y-1" role="alert">
        <p className="font-medium text-fg">This upload expired.</p>
        <p className="text-sm text-fg-secondary">Ask your AI app to start a new one.</p>
      </Card>
    );
  } else {
    body = (
      <Card padding="roomy" className="space-y-4">
        <div>
          <p className="font-medium text-fg">Your AI app asked for {kind === "image" ? "an image" : "a video"}.</p>
          <p className="text-sm text-fg-secondary">
            {limits?.formats ? `${limits.formats.join(", ").toUpperCase()}, ` : ""}up to {limits?.max_mb ?? 100} MB.
            The file goes straight to storage and into your media library.
          </p>
        </div>
        <input
          ref={input}
          type="file"
          accept={accept}
          className="sr-only"
          aria-label="Choose a file"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void send(file);
            event.target.value = "";
          }}
        />
        <Button type="button" disabled={progress !== null} onClick={() => input.current?.click()}>
          {progress === null ? "Choose a file" : `Uploading ${Math.round(progress * 100)}%`}
        </Button>
        {problem ? (
          <p role="alert" className="text-sm text-danger">
            {problem}
          </p>
        ) : null}
      </Card>
    );
  }

  return (
    <PageFrame title="Upload a file">
      <div className="max-w-xl">{body}</div>
    </PageFrame>
  );
}
