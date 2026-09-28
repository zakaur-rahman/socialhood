/**
 * Signed direct upload (TR-MED-01): ask the API for a signature, send the file straight to
 * Cloudinary (XMLHttpRequest, for the progress ring), then register the asset with the API.
 * The file never passes through our servers.
 */
import type { Api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/queries/unwrap";
import type { MediaAsset, Platform, ResourceType, UploadSignature } from "@/lib/api/types";

const KB = 1024;
const MB = 1024 * KB;

type FileKind = "image" | "video" | "audio" | "file";
type Rule = { label: string; extensions: string[]; maxBytes: number };

// The extension decides the kind: browsers report no MIME type for many documents.
const KIND_BY_EXTENSION: Record<string, FileKind> = {
  jpg: "image",
  jpeg: "image",
  png: "image",
  webp: "image",
  heic: "image",
  mp4: "video",
  mov: "video",
  webm: "video",
  avi: "video",
  "3gp": "video",
  mp3: "audio",
  m4a: "audio",
  aac: "audio",
  wav: "audio",
  ogg: "audio",
  opus: "audio",
  amr: "audio",
  pdf: "file",
  txt: "file",
  doc: "file",
  docx: "file",
  xls: "file",
  xlsx: "file",
  ppt: "file",
  pptx: "file",
};

// Meta's documented limits (Instagram Messaging; WhatsApp Cloud API media), as the API enforces
// them. Images are converted to JPEG and video to MP4 when sent, so any stored format works.
const RULES: Record<Platform, Partial<Record<FileKind, Rule>>> = {
  instagram: {
    image: { label: "Images", extensions: ["jpg", "jpeg", "png", "webp", "heic"], maxBytes: 8 * MB },
    video: { label: "Videos", extensions: ["mp4", "mov", "webm", "avi"], maxBytes: 25 * MB },
    audio: { label: "Audio files", extensions: ["aac", "m4a", "wav"], maxBytes: 25 * MB },
    file: { label: "Files", extensions: ["pdf"], maxBytes: 25 * MB },
  },
  whatsapp: {
    image: { label: "Images", extensions: ["jpg", "jpeg", "png", "webp", "heic"], maxBytes: 5 * MB },
    video: { label: "Videos", extensions: ["mp4", "mov", "3gp"], maxBytes: 16 * MB },
    audio: { label: "Audio files", extensions: ["aac", "amr", "mp3", "m4a", "ogg", "opus"], maxBytes: 16 * MB },
    file: {
      label: "Files",
      extensions: ["pdf", "txt", "doc", "docx", "xls", "xlsx", "ppt", "pptx"],
      maxBytes: 100 * MB,
    },
  },
};

const PLATFORM_NAME: Record<Platform, string> = { instagram: "Instagram", whatsapp: "WhatsApp" };

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : "";
}

function kindOf(file: Pick<File, "name" | "type">): FileKind | null {
  const byName = KIND_BY_EXTENSION[extensionOf(file.name)];
  if (byName) return byName;
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  if (file.type.startsWith("audio/")) return "audio";
  return null;
}

function formatSize(bytes: number): string {
  return bytes >= MB ? `${bytes / MB} MB` : `${bytes / KB} KB`;
}

/** Cloudinary's resource type: audio is stored as "video", documents as "raw". */
export function resourceTypeFor(file: Pick<File, "name" | "type">): ResourceType {
  const kind = kindOf(file);
  if (kind === "image") return "image";
  if (kind === "video" || kind === "audio") return "video";
  return "raw";
}

function checkFor(platform: Platform) {
  return (file: File): string | null => {
    const name = PLATFORM_NAME[platform];
    const kind = kindOf(file);
    const rule = kind ? RULES[platform][kind] : undefined;
    if (!rule || !rule.extensions.includes(extensionOf(file.name) || "")) {
      return `${name} can't send this type of file.`;
    }
    if (file.size > rule.maxBytes) return `${rule.label} can be up to ${formatSize(rule.maxBytes)} on ${name}.`;
    return null;
  };
}

function acceptFor(platform: Platform): string {
  return Object.values(RULES[platform])
    .flatMap((rule) => rule.extensions.map((extension) => `.${extension}`))
    .join(",");
}

/** What each platform accepts in a DM (FR-INB-08), for the file picker and a quick check. */
export const ATTACHMENT_RULES: Record<Platform, { accept: string; check: (file: File) => string | null }> = {
  instagram: { accept: acceptFor("instagram"), check: checkFor("instagram") },
  whatsapp: { accept: acceptFor("whatsapp"), check: checkFor("whatsapp") },
};

/** WhatsApp stickers: 512 x 512 WebP up to 500 KB (the API checks the size in pixels). */
export const STICKER_RULE = {
  accept: ".webp",
  check(file: File): string | null {
    if (extensionOf(file.name) !== "webp") return "Stickers are WebP images.";
    if (file.size > 500 * KB) return "Stickers can be up to 500 KB.";
    return null;
  },
};

export class UploadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UploadError";
  }
}

type UploadOptions = {
  onProgress?: (fraction: number) => void;
  signal?: AbortSignal;
};

/** POST the file to Cloudinary with the signed parameters; resolves with its public_id. */
export function sendToStorage(
  signature: UploadSignature,
  file: File,
  { onProgress, signal }: UploadOptions = {},
): Promise<{ public_id: string }> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    form.append("api_key", signature.api_key);
    form.append("timestamp", String(signature.timestamp));
    form.append("folder", signature.folder);
    form.append("signature", signature.signature);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", signature.upload_url);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(event.loaded / event.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const body = JSON.parse(xhr.responseText) as { public_id?: string };
          if (body.public_id) return resolve({ public_id: body.public_id });
        } catch {
          // fall through
        }
      }
      reject(new UploadError("The upload didn't finish. Try again."));
    };
    xhr.onerror = () => reject(new UploadError("The upload didn't finish. Check your connection and try again."));
    xhr.onabort = () => reject(new DOMException("Upload canceled", "AbortError"));
    signal?.addEventListener("abort", () => xhr.abort(), { once: true });
    xhr.send(form);
  });
}

/** The whole flow for one file: signature, direct upload, registration. */
export async function uploadAsset(api: Api, wid: string, file: File, options: UploadOptions = {}): Promise<MediaAsset> {
  const resource_type = resourceTypeFor(file);
  const signature = await unwrap(
    api.POST("/v1/w/{wid}/media-assets/upload-signature", {
      params: { path: { wid } },
      body: { resource_type, purpose: "message" },
    }),
  );
  const { public_id } = await sendToStorage(signature, file, options);
  return unwrap(api.POST("/v1/w/{wid}/media-assets", { params: { path: { wid } }, body: { public_id, resource_type } }));
}
