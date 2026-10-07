"use client";

import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Check, Copy, EllipsisVertical, RotateCw, Send, Trash2, Undo2 } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";

import type { ScheduleValue } from "@/components/inbox/ScheduleFields";
import { LEAVE_WARNING } from "@/components/settings/SaveBar";
import { BOTTOM_BAR, reserveBottomBar } from "@/components/shell/sticky-bar";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { ApiError, isPlanLimitError, toApiError } from "@/lib/api/errors";
import { useSocialAccounts } from "@/lib/api/queries";
import {
  composerKeys,
  useComposerDelete,
  useComposerDuplicate,
  useComposerHashtagGroups,
  useComposerPostingSlots,
  useComposerPost,
  useComposerPublishNow,
  useComposerQueue,
  useComposerSchedule,
  useComposerUnschedule,
  useSaveComposerPost,
} from "@/lib/api/queries/scheduledPosts";
import type { MediaAsset } from "@/lib/api/types";
import { errorMessage } from "@/lib/copy";
import { itemsFromErrors, localChecklist, mergeChecklist } from "@/lib/publishing/checklist";
import { renderCrop, type Cropper } from "@/lib/publishing/crop";
import {
  assetLabel,
  checkPostFile,
  deriveFormat,
  fromMediaAsset,
  fromPostAsset,
  handleOf,
  isEditable,
  MAX_ASSETS,
  MIN_SCHEDULE_LEAD_MS,
  publishingAccounts,
  STATUS_LABEL,
  STATUS_TONE,
  type AssetInfo,
} from "@/lib/publishing/rules";
import type { ChecklistItem, ScheduledPost } from "@/lib/publishing/types";
import { instagramAccountColors } from "@/lib/schedule/format";
import { toastError } from "@/lib/toast-error";
import { formatDayTime, toZonedInputs, zonedToDate } from "@/lib/tz";
import { useNow } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { accountChipId, AccountPicker } from "./AccountPicker";
import { AutomationSection } from "./AutomationSection";
import { accountCaptionId, CAPTION_ID, CaptionEditor, FIRST_COMMENT_ID, FirstCommentEditor } from "./CaptionEditor";
import { CropDialog } from "./CropDialog";
import { MediaLibraryDialog } from "./MediaLibraryDialog";
import { MEDIA_ADD_ID, mediaTileId, MediaTray, moveItem, type TrayEntry } from "./MediaTray";
import { PostChecklist } from "./PostChecklist";
import { PostPreview } from "./PostPreview";
import { StatusBanner } from "./StatusBanner";
import { toRequest, usePostDraft, type Draft, type PostSaveStatus } from "./use-post-draft";
import { useMediaUploads, type Uploader } from "./use-media-uploads";
import { sharedFreeTime, WHEN_DATE_ID, WhenSection, type QueuePreview, type WhenMode } from "./WhenSection";

export type ComposerDeps = {
  /** Tests pass fakes; the app uploads through the API and Cloudinary and crops on a canvas. */
  upload?: Uploader;
  cropper?: Cropper;
};

export function scheduleHref(slug: string): Route {
  return `/w/${slug}/schedule` as Route;
}

export function composerHref(slug: string, id: string): Route {
  return `/w/${slug}/schedule/${id}` as Route;
}

/**
 * UX-SCR-13 (F-13): loads the post, then the composer. The composer remounts when the post moves
 * between editable (draft, scheduled) and read-only (publishing and after), so what shows is
 * always the stored post in read-only states and the user's draft while editing.
 */
export function PostComposer({
  id,
  initialWhen = "time",
  upload,
  cropper,
}: {
  id: string;
  /** ?when=queue: the Schedule page's Add to queue opens a new draft in queue mode. */
  initialWhen?: WhenMode;
} & ComposerDeps) {
  const workspace = useCurrentWorkspace();
  const post = useComposerPost(workspace.id, id);
  if (post.isPending) return <ComposerSkeleton />;
  if (post.isError) {
    if (post.error instanceof ApiError && post.error.status === 404) {
      return (
        <EmptyState
          className="min-h-[60vh]"
          title="Post not found"
          body="It may have been deleted."
          action={
            <Link href={scheduleHref(workspace.slug)} className="text-sm text-brand-fg underline-offset-4 hover:underline">
              Back to Schedule
            </Link>
          }
        />
      );
    }
    return <ErrorState error={post.error} onRetry={() => void post.refetch()} />;
  }
  const phase = isEditable(post.data.status) ? "edit" : "view";
  return <Composer key={`${id}-${phase}`} initial={post.data} initialWhen={initialWhen} upload={upload} cropper={cropper} />;
}

function ComposerSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading" className="mx-auto w-full max-w-[1200px] p-4 md:p-6">
      <Skeleton className="h-8 w-40" />
      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4 lg:max-w-[640px]">
          {[20, 36, 44, 24].map((height, index) => (
            <Skeleton key={index} className="w-full rounded-xl" style={{ height: `${height * 4}px` }} />
          ))}
        </div>
        <Skeleton className="h-[520px] rounded-xl" />
      </div>
    </div>
  );
}

const PLACEHOLDER_ASSET = (id: string): AssetInfo => ({
  id,
  resource_type: "image",
  url: "",
  thumbnail_url: null,
  width: null,
  height: null,
  duration_s: null,
  name: null,
});

function Composer({
  initial,
  initialWhen,
  upload,
  cropper = renderCrop,
}: { initial: ScheduledPost; initialWhen: WhenMode } & ComposerDeps) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const slug = workspace.slug;
  const timeZone = workspace.timezone;
  const router = useRouter();
  const queryClient = useQueryClient();
  const now = useNow(30_000);

  const server = useComposerPost(wid, initial.id).data ?? initial;
  const postId = initial.id;
  const accountsQuery = useSocialAccounts(wid);
  const allAccounts = useMemo(() => accountsQuery.data ?? [], [accountsQuery.data]);
  const igAccounts = useMemo(() => publishingAccounts(allAccounts), [allAccounts]);
  // Each account's identity colour, as Schedule gives it (one rule, in lib/schedule/format).
  const identities = useMemo(() => instagramAccountColors(allAccounts), [allAccounts]);
  const groupsQuery = useComposerHashtagGroups(wid);
  const groups = groupsQuery.data ?? [];

  const editable = isEditable(server.status);
  const isDraft = server.status === "draft";
  const { draft, update, flush, settle, reset, discard, status: saveStatus, error: saveError, dirty } = usePostDraft(wid, initial, {
    autosave: isDraft,
  });

  // Failures from the last rejected action (a 422), shown in the checklist until the next edit.
  const [actionErrors, setActionErrors] = useState<ChecklistItem[]>([]);
  const change = useCallback(
    (patch: Partial<Draft> | ((current: Draft) => Partial<Draft>)) => {
      update(patch);
      setActionErrors([]);
    },
    [update],
  );

  // ---- media: what is known about each asset, uploads, crop, library
  const [localAssets, setLocalAssets] = useState<Record<string, AssetInfo>>({});
  // Photos picked in this session, so a crop reads the file instead of downloading it again.
  const [localFiles, setLocalFiles] = useState<Record<string, File>>({});
  const assets = useMemo(() => {
    const map: Record<string, AssetInfo> = { ...localAssets };
    for (const asset of [...initial.assets, ...server.assets]) {
      map[asset.id] = { ...fromPostAsset(asset), name: localAssets[asset.id]?.name ?? null };
    }
    return map;
  }, [initial.assets, localAssets, server.assets]);

  const remember = (list: MediaAsset[]) =>
    setLocalAssets((current) => {
      const next = { ...current };
      for (const asset of list) {
        const info = fromMediaAsset(asset);
        if (info) next[info.id] = info;
      }
      return next;
    });

  const uploads = useMediaUploads(wid, {
    upload,
    onUploaded: (asset, item) => {
      if (asset.resource_type !== "image" && asset.resource_type !== "video") return;
      remember([asset]);
      if (asset.resource_type === "image") setLocalFiles((current) => ({ ...current, [asset.id]: item.file }));
      change((current) => {
        if (item.replaces) {
          // A crop takes the photo's place; if the photo was removed meanwhile, the crop is dropped.
          return current.asset_ids.includes(item.replaces)
            ? { asset_ids: current.asset_ids.map((id) => (id === item.replaces ? asset.id : id)) }
            : {};
        }
        if (current.asset_ids.includes(asset.id)) return {};
        return { asset_ids: [...current.asset_ids, asset.id].slice(0, MAX_ASSETS) };
      });
    },
  });
  const newUploads = uploads.items.filter((item) => !item.replaces);
  const [fileNotice, setFileNotice] = useState<string | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [cropId, setCropId] = useState<string | null>(null);

  const addFiles = (files: File[]) => {
    let room = MAX_ASSETS - draft.asset_ids.length - newUploads.length;
    const problems: string[] = [];
    for (const file of files) {
      const problem = checkPostFile(file);
      if (problem) {
        problems.push(`${file.name}: ${problem}`);
        continue;
      }
      if (room <= 0) {
        problems.push(`A post can have up to ${MAX_ASSETS} photos and videos.`);
        break;
      }
      uploads.add(file);
      room -= 1;
    }
    setFileNotice(problems.length ? problems.join(" ") : null);
  };

  const addFromLibrary = (picked: MediaAsset[]) => {
    remember(picked);
    change((current) => ({
      asset_ids: [...current.asset_ids, ...picked.map((asset) => asset.id).filter((id) => !current.asset_ids.includes(id))].slice(
        0,
        MAX_ASSETS,
      ),
    }));
  };

  const entries: TrayEntry[] = draft.asset_ids.map((id) => ({
    asset: assets[id] ?? PLACEHOLDER_ASSET(id),
    replacing: uploads.items.find((item) => item.replaces === id) ?? null,
  }));
  const postAssets = entries.map((entry) => entry.asset);
  const format = deriveFormat(postAssets);
  const cropIndex = cropId ? draft.asset_ids.indexOf(cropId) : -1;
  const cropAsset = cropId ? assets[cropId] : undefined;

  // ---- accounts and captions (per account when switched on)
  const [perAccount, setPerAccount] = useState(() => initial.targets.some((target) => target.caption_override != null));
  const selectedIds = draft.targets.map((target) => target.social_account_id);
  const selectedAccounts = selectedIds
    .map((accountId) => allAccounts.find((account) => account.id === accountId))
    .filter((account): account is NonNullable<typeof account> => Boolean(account));

  const toggleAccount = (accountId: string) => {
    const removing = draft.targets.some((target) => target.social_account_id === accountId);
    const remaining = draft.targets.filter((target) => target.social_account_id !== accountId);
    if (removing && perAccount && remaining.length < 2) setPerAccount(false);
    change((current) => {
      if (!current.targets.some((target) => target.social_account_id === accountId)) {
        return {
          targets: [...current.targets, { social_account_id: accountId, caption_override: perAccount ? current.caption : null }],
        };
      }
      const targets = current.targets.filter((target) => target.social_account_id !== accountId);
      if (!perAccount) return { targets };
      const firstCaption = targets[0]?.caption_override ?? current.caption;
      if (targets.length < 2) {
        return { caption: firstCaption, targets: targets.map((target) => ({ ...target, caption_override: null })) };
      }
      return { caption: firstCaption, targets };
    });
  };

  const onPerAccountChange = (on: boolean) => {
    setPerAccount(on);
    change((current) =>
      on
        ? { targets: current.targets.map((target) => ({ ...target, caption_override: current.caption })) }
        : {
            caption: current.targets[0]?.caption_override ?? current.caption,
            targets: current.targets.map((target) => ({ ...target, caption_override: null })),
          },
    );
  };

  const captionFor = (accountId: string | null): string => {
    const target = draft.targets.find((item) => item.social_account_id === accountId);
    return perAccount && target?.caption_override != null ? target.caption_override : draft.caption;
  };
  const captionsDiffer = perAccount && new Set(draft.targets.map((target) => target.caption_override ?? draft.caption)).size > 1;

  // ---- when
  const [whenMode, setWhenMode] = useState<WhenMode>(initialWhen === "queue" && initial.status === "draft" ? "queue" : "time");
  const [when, setWhen] = useState<ScheduleValue>(() =>
    initial.publish_at ? toZonedInputs(new Date(initial.publish_at), timeZone) : { date: "", time: "" },
  );
  const timeAt = zonedToDate(when.date, when.time, timeZone);
  const timeError =
    timeAt && timeAt.getTime() - now.getTime() < MIN_SCHEDULE_LEAD_MS ? "Pick a time at least 5 minutes from now." : null;

  const onWhenChange = (value: ScheduleValue) => {
    setWhen(value);
    const at = zonedToDate(value.date, value.time, timeZone);
    change({ publish_at: at ? at.toISOString() : null });
  };

  const onModeChange = (mode: WhenMode) => {
    setWhenMode(mode);
    // Add to queue picks the time; a time left on the draft would only fail the checklist.
    change({ publish_at: mode === "queue" ? null : (timeAt?.toISOString() ?? null) });
  };

  const queueWanted = editable && isDraft && whenMode === "queue";
  const slotQueries = useComposerPostingSlots(wid, selectedIds, queueWanted);
  let queue: QueuePreview;
  if (selectedIds.length === 0) queue = { state: "no-accounts" };
  else if (slotQueries.some((query) => query.isError)) queue = { state: "error" };
  else if (slotQueries.some((query) => !query.data)) queue = { state: "loading" };
  else {
    const missing = slotQueries
      .map((query, index) => (query.data?.slots.length ? null : handleOf(allAccounts.find((account) => account.id === selectedIds[index]))))
      .filter((handle): handle is string => Boolean(handle));
    const shared = sharedFreeTime(slotQueries.map((query) => query.data?.next_free_at ?? []));
    queue = missing.length ? { state: "missing", handles: missing } : shared ? { state: "ready", at: shared } : { state: "later" };
  }

  // ---- checklist (FR-PUB-10)
  const local = localChecklist({ draft, accounts: allAccounts, assets, now });
  const saveProblems = saveError?.code === "validation_error" ? itemsFromErrors(saveError.errors) : [];
  const checklist = mergeChecklist(local, server.checklist, saveStatus === "saved", [...actionErrors, ...saveProblems]);
  const failingExceptTime = checklist.items.filter((item) => !item.ok && item.key !== "publish_at").length;

  const fieldTarget = (field: string | null | undefined): string => {
    if (!field || field === "targets") return "composer-accounts";
    let match = /^targets\.(\d+)\.caption_override$/.exec(field);
    if (match) {
      const target = draft.targets[Number(match[1])];
      return target && perAccount ? accountCaptionId(target.social_account_id) : CAPTION_ID;
    }
    match = /^targets\.(\d+)/.exec(field);
    if (match) {
      const target = draft.targets[Number(match[1])];
      return target ? accountChipId(target.social_account_id) : "composer-accounts";
    }
    match = /^asset_ids\.(\d+)/.exec(field);
    if (match) {
      const assetId = draft.asset_ids[Number(match[1])];
      return assetId ? mediaTileId(assetId) : MEDIA_ADD_ID;
    }
    if (field.startsWith("asset_ids")) return MEDIA_ADD_ID;
    if (field === "caption") return perAccount && draft.targets[0] ? accountCaptionId(draft.targets[0].social_account_id) : CAPTION_ID;
    if (field === "first_comment") return FIRST_COMMENT_ID;
    if (field.startsWith("publish_at")) return WHEN_DATE_ID;
    return "composer-accounts";
  };

  const focusField = (field: string | null | undefined) => {
    if (field?.startsWith("publish_at") && whenMode !== "time") setWhenMode("time");
    requestAnimationFrame(() => {
      const element = document.getElementById(fieldTarget(field));
      if (!element) return;
      const target = element.querySelector<HTMLElement>("[data-focus-target]") ?? element;
      target.scrollIntoView?.({ block: "center", behavior: "smooth" });
      target.focus({ preventScroll: true });
    });
  };

  // ---- actions
  const schedule = useComposerSchedule(wid, postId);
  const queuePost = useComposerQueue(wid, postId);
  const publishNow = useComposerPublishNow(wid, postId);
  const unschedule = useComposerUnschedule(wid, postId);
  const put = useSaveComposerPost(wid, postId);
  const duplicate = useComposerDuplicate(wid);
  const remove = useComposerDelete(wid);
  const [confirmPublish, setConfirmPublish] = useState(false);
  const [confirmUnschedule, setConfirmUnschedule] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const acting = schedule.isPending || queuePost.isPending || publishNow.isPending || unschedule.isPending || put.isPending;

  const onActionError = (caught: unknown) => {
    // Over the plan's scheduled posts (402): the upgrade dialog names the limit, alone.
    if (isPlanLimitError(caught)) return;
    const apiError = toApiError(caught);
    if (apiError.code === "validation_error" && apiError.errors.length) {
      setActionErrors(itemsFromErrors(apiError.errors));
      toast.error(
        apiError.errors.length === 1 ? "One thing to fix in the checklist." : `${apiError.errors.length} things to fix in the checklist.`,
      );
      return;
    }
    toastError(apiError);
    // Publishing started elsewhere, or the post changed: show what is stored now.
    if (apiError.status === 409) void queryClient.invalidateQueries({ queryKey: composerKeys.post(wid, postId) });
  };

  /** Stored post after a lifecycle action: it becomes the draft, and its time fills When. */
  const afterAction = (post: ScheduledPost) => {
    reset(post);
    setActionErrors([]);
    if (post.publish_at) setWhen(toZonedInputs(new Date(post.publish_at), timeZone));
    setWhenMode("time");
  };

  /** A draft's pending edits go first, so the API schedules what is on screen. */
  const saveFirst = async (): Promise<boolean> => {
    if (await settle()) return true;
    toast.error("Your latest changes aren't saved yet. Fix what's marked, then try again.");
    return false;
  };

  const onSaveDraft = async () => {
    if (await saveFirst()) toast.success("Draft saved.");
  };

  /** ⋯ Unschedule, once confirmed: the post goes back to the drafts, with its edits. */
  const onUnschedule = async () => {
    setConfirmUnschedule(false);
    try {
      await unschedule.mutateAsync();
      const post = await put.mutateAsync(toRequest(draft));
      afterAction(post);
      toast.success("Moved to drafts. It won't publish until you schedule it again.");
    } catch (caught) {
      onActionError(caught);
    }
  };

  const onSchedule = async () => {
    if (!isDraft) {
      put.mutate(toRequest(draft), {
        onSuccess: (post) => {
          afterAction(post);
          toast.success(post.publish_at ? `Schedule updated. It publishes ${formatDayTime(post.publish_at, timeZone)}.` : "Schedule updated.");
        },
        onError: onActionError,
      });
      return;
    }
    if (!(await saveFirst())) return;
    if (whenMode === "queue") {
      queuePost.mutate(undefined, {
        onSuccess: (post) => {
          afterAction(post);
          toast.success(post.publish_at ? `Added to the queue for ${formatDayTime(post.publish_at, timeZone)}.` : "Added to the queue.");
        },
        onError: onActionError,
      });
      return;
    }
    if (!timeAt) return;
    schedule.mutate(timeAt.toISOString(), {
      onSuccess: (post) => {
        afterAction(post);
        toast.success(`Scheduled for ${formatDayTime(post.publish_at ?? timeAt, timeZone)}.`);
      },
      onError: onActionError,
    });
  };

  const onPublishNow = async () => {
    setConfirmPublish(false);
    try {
      if (isDraft) {
        if (!(await saveFirst())) return;
      } else if (dirty) {
        reset(await put.mutateAsync(toRequest(draft)));
      }
      const post = await publishNow.mutateAsync();
      reset(post);
      toast.success("Publishing started.");
    } catch (caught) {
      onActionError(caught);
    }
  };

  const onEditAndRetry = () =>
    put.mutate(toRequest(draft), {
      onSuccess: () => toast.success("Back to draft. Fix what's needed, then schedule it again."),
      onError: onActionError,
    });

  const onDuplicate = async () => {
    if (isDraft) await settle();
    // The copy opens in its own composer. A scheduled post's edits aren't saved until Update
    // schedule, so leaving for the copy asks first, as a link out of the page does (useLeaveWarning).
    else if (dirty && !window.confirm(LEAVE_WARNING)) return;
    duplicate.mutate(postId, {
      onSuccess: (copy) => {
        toast.success("Duplicated. You're editing the copy.");
        router.push(composerHref(slug, copy.id));
      },
      onError: (caught) => toastError(caught),
    });
  };

  const onDelete = () =>
    remove.mutate(postId, {
      onSuccess: () => {
        discard();
        toast.success("Post deleted.");
        router.push(scheduleHref(slug));
      },
      onError: (caught) => toastError(caught),
    });

  // ---- what the buttons can do now, and why not (UX-SCR-13: disabled buttons say why)
  const fixText = checklist.failing === 1 ? "Fix the item in the checklist" : `Fix the ${checklist.failing} items in the checklist`;
  let scheduleBlock: string | null = null;
  if (!checklist.ready) scheduleBlock = `${fixText} to ${isDraft ? "schedule" : "update the schedule"}.`;
  else if (uploads.busy) scheduleBlock = "Wait for the uploads to finish.";
  else if (isDraft && whenMode === "queue" && queue.state === "missing") scheduleBlock = "Set posting times for every account, or pick a time.";
  else if ((!isDraft || whenMode === "time") && !timeAt) scheduleBlock = isDraft ? "Pick a date and time, or add the post to the queue." : "Pick a date and time.";
  else if (!isDraft && !dirty) scheduleBlock = "Change something to update the schedule.";
  let publishBlock: string | null = null;
  if (failingExceptTime > 0) publishBlock = `Fix the checklist to publish now.`;
  else if (uploads.busy) publishBlock = "Wait for the uploads to finish.";
  // When both buttons are blocked for the same reason, it is said once, for both of them.
  const publishReason = publishBlock !== scheduleBlock ? publishBlock : null;
  const publishReasonId = publishReason ? "composer-publish-reason" : publishBlock ? "composer-schedule-reason" : undefined;
  const scheduleLabel = !isDraft ? "Update schedule" : whenMode === "queue" ? "Add to queue" : "Schedule";

  const publishAtLabel = server.status === "scheduled" && server.publish_at ? server.publish_at : null;

  return (
    <div className="mx-auto w-full max-w-[1200px] p-4 md:p-6">
      {/* The title row keeps More beside the title on phones (UI-ISS-115): the status and save
          state wrap inside their own group instead of pushing More onto a line of its own. */}
      <header className="flex items-center gap-3 border-b border-line pb-4">
        <div className="min-w-max flex-1">
          <nav aria-label="Breadcrumb" className="text-xs text-fg-secondary">
            <Link href={scheduleHref(slug)} className="hover:text-fg hover:underline">
              Schedule
            </Link>{" "}
            <span aria-hidden>/</span>
          </nav>
          <h1 className="text-2xl font-semibold tracking-tight">Post</h1>
        </div>
        <div className="flex min-w-0 flex-wrap items-center justify-end gap-x-3 gap-y-1">
          <span data-testid="status-pill" className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", STATUS_TONE[server.status])}>
            {STATUS_LABEL[server.status]}
          </span>
          {editable ? <SaveState status={saveStatus} autosave={isDraft} onRetry={() => void flush()} /> : null}
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-lg" aria-label="More actions">
              <EllipsisVertical aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => void onDuplicate()} disabled={duplicate.isPending}>
              <Copy aria-hidden /> Duplicate
            </DropdownMenuItem>
            {server.status === "scheduled" ? (
              <DropdownMenuItem onSelect={() => setConfirmUnschedule(true)} disabled={acting}>
                <Undo2 aria-hidden /> Unschedule
              </DropdownMenuItem>
            ) : null}
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={() => setConfirmDelete(true)} disabled={server.status === "publishing"}>
              <Trash2 aria-hidden /> Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>
      {saveStatus === "error" && saveError && saveError.code !== "validation_error" ? (
        <p role="alert" className="mt-3 flex items-start gap-2 text-sm text-danger-fg">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          {errorMessage(saveError)}
        </p>
      ) : null}

      <StatusBanner
        post={server}
        accounts={allAccounts}
        timeZone={timeZone}
        now={now}
        onEditAndRetry={onEditAndRetry}
        retrying={put.isPending}
      />

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-4 lg:max-w-[640px]">
          <fieldset disabled={!editable} className="min-w-0 space-y-4">
            <legend className="sr-only">{editable ? "Post" : "Post (read-only)"}</legend>
            <AccountPicker
              accounts={igAccounts}
              loading={accountsQuery.isPending}
              selected={selectedIds}
              onToggle={toggleAccount}
              slug={slug}
            />
            <MediaTray
              entries={entries}
              uploads={newUploads}
              format={format}
              notice={fileNotice}
              readOnly={!editable}
              onFiles={addFiles}
              onOpenLibrary={() => setLibraryOpen(true)}
              onRemove={(assetId) => change((current) => ({ asset_ids: current.asset_ids.filter((id) => id !== assetId) }))}
              onMove={(from, to) => change((current) => ({ asset_ids: moveItem(current.asset_ids, from, to) }))}
              onCrop={setCropId}
              onRetryUpload={uploads.retry}
              onRemoveUpload={uploads.remove}
            />
            <CaptionEditor
              wid={wid}
              slug={slug}
              groups={groups}
              groupsLoading={groupsQuery.isPending}
              caption={draft.caption}
              onCaptionChange={(caption) => change({ caption })}
              perAccount={perAccount}
              canPerAccount={draft.targets.length > 1}
              onPerAccountChange={onPerAccountChange}
              accountCaptions={draft.targets.map((target) => ({
                accountId: target.social_account_id,
                label: handleOf(allAccounts.find((account) => account.id === target.social_account_id)),
                value: target.caption_override ?? draft.caption,
              }))}
              onAccountCaptionChange={(index, value) =>
                change((current) => ({
                  targets: current.targets.map((target, position) => (position === index ? { ...target, caption_override: value } : target)),
                  ...(index === 0 ? { caption: value } : {}),
                }))
              }
            />
            <FirstCommentEditor
              wid={wid}
              slug={slug}
              groups={groups}
              groupsLoading={groupsQuery.isPending}
              value={draft.first_comment ?? ""}
              onChange={(value) => change({ first_comment: value })}
            />
            <AutomationSection
              wid={wid}
              slug={slug}
              postId={postId}
              linked={server.automations}
              accounts={selectedAccounts.filter((account) => account.platform === "instagram")}
              plan={workspace.plan}
              readOnly={!editable}
              beforeCreate={isDraft ? settle : async () => !dirty}
            />
            {editable ? (
              <WhenSection
                mode={isDraft ? whenMode : "time"}
                onModeChange={onModeChange}
                value={when}
                onChange={onWhenChange}
                timeZone={timeZone}
                error={timeError}
                queue={queue}
                scheduledAt={publishAtLabel}
                allowQueue={isDraft}
                slug={slug}
                now={now}
              />
            ) : null}
          </fieldset>

          {editable ? (
            <>
              <PostChecklist
                items={checklist.items}
                failing={checklist.failing}
                hrefFor={(field) => `#${fieldTarget(field)}`}
                onFix={focusField}
              />
              {/* Sticky, but never over the focused control, and in the flow on short viewports (UI-ISS-014). */}
              <div
                ref={reserveBottomBar}
                role="region"
                aria-label="Post actions"
                className={cn(
                  "sticky bottom-0 z-10 -mx-4 border-t border-line bg-canvas px-4 py-3 md:mx-0 md:rounded-xl md:border md:bg-panel",
                  BOTTOM_BAR,
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  {/* A scheduled post saves with Update schedule; unscheduling is in ⋯ and asks first. */}
                  {isDraft ? (
                    <Button variant="ghost" size="lg" onClick={() => void onSaveDraft()} disabled={acting}>
                      Save draft
                    </Button>
                  ) : null}
                  <Button
                    variant="secondary"
                    size="lg"
                    disabled={Boolean(publishBlock) || acting}
                    aria-describedby={publishReasonId}
                    onClick={() => setConfirmPublish(true)}
                  >
                    {publishNow.isPending ? <Spinner /> : <Send aria-hidden />}
                    Publish now
                  </Button>
                  <Button
                    size="lg"
                    className="ml-auto"
                    disabled={Boolean(scheduleBlock) || acting}
                    aria-describedby={scheduleBlock ? "composer-schedule-reason" : undefined}
                    onClick={() => void onSchedule()}
                  >
                    {schedule.isPending || queuePost.isPending || (put.isPending && !isDraft) ? <Spinner /> : null}
                    {scheduleLabel}
                  </Button>
                </div>
                {scheduleBlock || publishReason ? (
                  // On a short viewport the reasons share one line; the buttons keep the full text
                  // through aria-describedby, and the checklist above lists every item to fix.
                  <div className="mt-2 space-y-1 text-xs text-fg-secondary short:truncate">
                    {scheduleBlock ? (
                      <p id="composer-schedule-reason" className="short:inline" data-testid="schedule-reason">
                        {scheduleLabel}
                        {publishBlock === scheduleBlock ? " and Publish now" : ""}: {scheduleBlock}
                      </p>
                    ) : null}{" "}
                    {publishReason ? (
                      <p id="composer-publish-reason" className="short:inline">
                        Publish now: {publishReason}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </>
          ) : null}
        </div>

        <aside aria-label="Preview" className="min-w-0 lg:sticky lg:top-6 lg:self-start">
          <PostPreview
            wid={wid}
            accounts={selectedAccounts}
            identities={identities}
            captionFor={captionFor}
            captionsDiffer={captionsDiffer}
            assets={postAssets.filter((asset) => asset.url)}
            format={format}
            firstComment={draft.first_comment}
          />
        </aside>
      </div>

      {libraryOpen ? (
        <MediaLibraryDialog
          open={libraryOpen}
          onOpenChange={setLibraryOpen}
          wid={wid}
          inPost={draft.asset_ids}
          slots={Math.max(0, MAX_ASSETS - draft.asset_ids.length - newUploads.length)}
          onAdd={addFromLibrary}
        />
      ) : null}
      {cropId && cropAsset ? (
        <CropDialog
          key={cropId}
          open
          onOpenChange={(open) => !open && setCropId(null)}
          asset={cropAsset}
          label={assetLabel(cropAsset, Math.max(0, cropIndex))}
          source={{ file: localFiles[cropId] ?? null, url: cropAsset.url, name: cropAsset.name ?? "photo.jpg" }}
          cropper={cropper}
          onCropped={(file) => uploads.add(file, cropId)}
        />
      ) : null}

      <AlertDialog open={confirmPublish} onOpenChange={setConfirmPublish}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Publish now?</AlertDialogTitle>
            <AlertDialogDescription>
              It goes live on {selectedAccounts.map((account) => handleOf(account)).join(", ") || "the selected accounts"} straight away.
              You can&apos;t change it once publishing starts.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void onPublishNow()}>Publish now</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={confirmUnschedule} onOpenChange={setConfirmUnschedule}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unschedule this post?</AlertDialogTitle>
            <AlertDialogDescription>It won&apos;t publish until you schedule it again.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void onUnschedule()}>Unschedule</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this post?</AlertDialogTitle>
            <AlertDialogDescription>
              {server.status === "published" || server.status === "partially_published"
                ? "It stays on Instagram and in Comments; only the Schedule copy is removed."
                : "It won't be published, and it can't be restored."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={onDelete}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

/** Drafts: "Saved" once the API has the latest edit. Scheduled posts: edits wait for Update schedule. */
function SaveState({ status, autosave, onRetry }: { status: PostSaveStatus; autosave: boolean; onRetry: () => void }) {
  return (
    <div className="flex items-center gap-2 text-xs text-fg-secondary">
      <p role="status" aria-live="polite" data-testid="save-status" className="flex items-center gap-1">
        {status === "saved" ? (
          <>
            <Check className="size-3.5" aria-hidden /> Saved
          </>
        ) : status === "saving" ? (
          <>
            <Spinner size="sm" /> Saving…
          </>
        ) : status === "unsaved" ? (
          "Unsaved changes"
        ) : (
          <span className="flex items-center gap-1 text-danger-fg">
            <AlertCircle className="size-3.5" aria-hidden /> Not saved
          </span>
        )}
      </p>
      {status === "error" && autosave ? (
        <Button variant="ghost" size="sm" onClick={onRetry}>
          <RotateCw aria-hidden /> Retry
        </Button>
      ) : null}
    </div>
  );
}
