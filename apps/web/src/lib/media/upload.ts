/**
 * Signed direct upload (TR-MED-01): ask the API for a signature, send the file straight to
 * Cloudinary (XMLHttpRequest, for the progress ring), then register the asset with the API.
 * The file never passes through our servers.
 */
import type { Api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/queries/unwrap";
import type { MediaAsset, Platform, ResourceType, UploadSignature } from "@/lib/api/types";

export function resourceTypeFor(file: Pick<File, "type">): ResourceType {
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  return "raw";
}

const MB = 1024 * 1024;

/** What each platform accepts in a DM (FR-INB-08, TR-MED-02), for the file picker and a quick check. */
export const ATTACHMENT_RULES: Record<Platform, { accept: string; check: (file: File) => string | null }> = {
  instagram: {
    accept: "image/jpeg,image/png,image/webp,image/heic",
    check: (file) => {
      if (!file.type.startsWith("image/")) return "Instagram DMs accept images only.";
      if (file.size > 8 * MB) return "Images can be up to 8 MB.";
      return null;
    },
  },
  whatsapp: {
    accept: "image/jpeg,image/png,image/webp,video/mp4,video/quicktime,application/pdf",
    check: (file) => {
      if (file.type.startsWith("image/")) return file.size > 8 * MB ? "Images can be up to 8 MB." : null;
      if (file.type.startsWith("video/")) return file.size > 100 * MB ? "Videos can be up to 100 MB." : null;
      if (file.type === "application/pdf") return file.size > 20 * MB ? "PDFs can be up to 20 MB." : null;
      return "WhatsApp accepts images, MP4 or MOV video, and PDF documents.";
    },
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
