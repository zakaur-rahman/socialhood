/**
 * The crop tool (TR-MED-02, UX-SCR-13): an image outside 4:5 to 1.91:1 is cropped to 1:1, 4:5 or
 * 1.91:1 in the browser and uploaded as a new file, which takes the old one's place in the post.
 */

export type CropRatio = { key: "1:1" | "4:5" | "1.91:1"; value: number; label: string };

export const CROP_RATIOS: readonly CropRatio[] = [
  { key: "1:1", value: 1, label: "Square 1:1" },
  { key: "4:5", value: 4 / 5, label: "Portrait 4:5" },
  { key: "1.91:1", value: 1.91, label: "Landscape 1.91:1" },
];

export type Rect = { x: number; y: number; width: number; height: number };

/** The ratio closest to the image's: a tall image becomes 4:5, a wide one 1.91:1. */
export function suggestedRatio(width: number, height: number): CropRatio {
  const ratio = width / height;
  let best = CROP_RATIOS[0];
  for (const option of CROP_RATIOS) {
    if (Math.abs(Math.log(option.value / ratio)) < Math.abs(Math.log(best.value / ratio))) best = option;
  }
  return best;
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

/**
 * The largest rectangle of the ratio inside the image, centred on ``focus`` (0 to 1 along each
 * axis) as far as the edges allow. Whole pixels.
 */
export function cropRect(width: number, height: number, ratio: number, focus = { x: 0.5, y: 0.5 }): Rect {
  let cropWidth = width;
  let cropHeight = Math.round(width / ratio);
  if (cropHeight > height) {
    cropHeight = height;
    cropWidth = Math.round(height * ratio);
  }
  const x = Math.round(clamp(focus.x * width - cropWidth / 2, 0, width - cropWidth));
  const y = Math.round(clamp(focus.y * height - cropHeight / 2, 0, height - cropHeight));
  return { x, y, width: cropWidth, height: cropHeight };
}

/** The focus point after moving the frame by a fraction of the image (arrow keys, dragging). */
export function moveFocus(focus: { x: number; y: number }, dx: number, dy: number): { x: number; y: number } {
  return { x: clamp(focus.x + dx, 0, 1), y: clamp(focus.y + dy, 0, 1) };
}

/** The focus that keeps a rectangle where it is (so the frame doesn't jump when the ratio changes). */
export function focusOf(rect: Rect, width: number, height: number): { x: number; y: number } {
  return { x: (rect.x + rect.width / 2) / width, y: (rect.y + rect.height / 2) / height };
}

/** Instagram publishes at most 1440 px wide (TR-MED-02 delivery); keep a little more for quality. */
const MAX_OUTPUT_EDGE = 2160;

export type CropSource = { file: File | null; url: string; name: string };

export class CropError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CropError";
  }
}

function loadImage(src: string, crossOrigin: boolean): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    if (crossOrigin) image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = () => reject(new CropError("This image couldn't be opened for cropping."));
    image.src = src;
  });
}

function croppedName(name: string, ratio: CropRatio): string {
  const base = name.replace(/\.[^.]+$/, "") || "photo";
  return `${base}-${ratio.key.replace(/[:.]/g, "x")}.jpg`;
}

/**
 * Draw the rectangle of the image onto a canvas and return it as a JPEG file. The file just
 * picked is used when it is still in memory; otherwise the uploaded copy is read (Cloudinary
 * serves it with CORS, so the canvas stays readable).
 */
export async function renderCrop(source: CropSource, rect: Rect, ratio: CropRatio): Promise<File> {
  const objectUrl = source.file ? URL.createObjectURL(source.file) : null;
  try {
    const image = await loadImage(objectUrl ?? source.url, !objectUrl);
    const scale = Math.min(1, MAX_OUTPUT_EDGE / Math.max(rect.width, rect.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(rect.width * scale);
    canvas.height = Math.round(rect.height * scale);
    const context = canvas.getContext("2d");
    if (!context) throw new CropError("This browser can't crop images. Crop it on your device and upload it again.");
    context.drawImage(image, rect.x, rect.y, rect.width, rect.height, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve, reject) => {
      try {
        canvas.toBlob(resolve, "image/jpeg", 0.92);
      } catch {
        reject(new CropError("This image can't be cropped here. Crop it on your device and upload it again."));
      }
    });
    if (!blob) throw new CropError("This image can't be cropped here. Crop it on your device and upload it again.");
    return new File([blob], croppedName(source.name, ratio), { type: "image/jpeg" });
  } finally {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  }
}

export type Cropper = typeof renderCrop;
