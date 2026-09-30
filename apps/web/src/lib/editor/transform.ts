/**
 * (asset, edit spec) → a Cloudinary transformation and URL (P7b: TR-MED-04).
 *
 * A line-for-line twin of apps/api/src/socialhood/media/editor/transform.py: the editor's previews
 * are the files that get published. Both run every golden case in
 * packages/editor-fixtures/transform-cases.json (transform.test.ts here, test_editor_transform.py
 * there), so change both together and regenerate the fixtures (apps/api/scripts/editor_fixtures.py).
 * The component order and number formatting are documented in the Python module.
 */
import {
  ADJUSTMENT_ORDER,
  ADJUSTMENTS,
  ASPECTS,
  COOL_RGB,
  FONTS,
  MAX_WIDTH,
  PHOTO_ONLY_ADJUSTMENTS,
  PRESETS,
  SPEEDS,
  TEXT_MAX_WIDTH,
  TEXT_PADDING,
  WARM_RGB,
  WARMTH_MAX_ALPHA,
  normalizeSpec,
  type AdjustmentName,
  type EditSpec,
  type MediaKind,
  type PartialEditSpec,
  type TextLayer,
} from "./spec";

export const DELIVERY_BASE = "https://res.cloudinary.com";
export const IMAGE_DELIVERY = "q_auto";
export const VIDEO_DELIVERY = "vc_h264,ac_aac,q_auto";

/** What the builder needs of an upload (PostAsset: public_id, size; the cloud from its URL). */
export type AssetMeta = {
  cloud_name: string;
  public_id: string;
  resource_type: MediaKind;
  width: number;
  height: number;
  duration_s?: number | null;
};

export type Built = {
  kind: MediaKind;
  transformation: string;
  format: "jpg" | "mp4";
  url: string;
  width: number;
  height: number;
  duration_s: number | null;
};

export class TransformError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TransformError";
  }
}

/** The cloud an upload's delivery URL names (https://res.cloudinary.com/{cloud}/…), or null. */
export function cloudNameOf(url: string): string | null {
  const match = /^https:\/\/res\.cloudinary\.com\/([^/]+)\//.exec(url);
  return match ? match[1] : null;
}

/** An upload as the builder needs it; null when it can't be edited (no size or no cloud). */
export function assetMetaOf(asset: {
  public_id: string;
  resource_type: MediaKind;
  url: string;
  width?: number | null;
  height?: number | null;
  duration_s?: number | null;
}): AssetMeta | null {
  const cloud = cloudNameOf(asset.url);
  if (!cloud || !asset.width || !asset.height) return null;
  return {
    cloud_name: cloud,
    public_id: asset.public_id,
    resource_type: asset.resource_type,
    width: asset.width,
    height: asset.height,
    duration_s: asset.duration_s ?? null,
  };
}

// ---------------------------------------------------------------- numbers and text

/** Round half up, as the Python twin does. */
export function rhu(value: number): number {
  return Math.floor(value + 0.5);
}

/** A time with at most two decimals and no trailing zeros ("1.5", "2", "0.25"). */
export function fmt(value: number): string {
  const hundredths = rhu(value * 100);
  const sign = hundredths < 0 ? "-" : "";
  const whole = Math.floor(Math.abs(hundredths) / 100);
  const frac = Math.abs(hundredths) % 100;
  if (frac === 0) return `${sign}${whole}`;
  return `${sign}${whole}.${String(frac).padStart(2, "0")}`.replace(/0+$/, "");
}

const UNRESERVED = /^[A-Za-z0-9\-_.~]$/;
const TWICE: Record<string, string> = { ",": "%252C", "/": "%252F", "%": "%2525" };

/** The text without characters Cloudinary can't draw (outside the BMP, lone surrogates). */
export function drawable(text: string): string {
  let kept = "";
  for (const ch of text) {
    const code = ch.codePointAt(0) ?? 0;
    if (code > 0xffff || (code >= 0xd800 && code <= 0xdfff)) continue;
    kept += ch;
  }
  return kept;
}

const HEX = (byte: number) => byte.toString(16).toUpperCase().padStart(2, "0");

/** Percent-encoded UTF-8, with "," "/" and "%" encoded twice (Cloudinary's text layers). */
export function encodeText(text: string): string {
  let out = "";
  for (const byte of new TextEncoder().encode(drawable(text))) {
    const ch = String.fromCharCode(byte);
    if (byte < 0x80 && UNRESERVED.test(ch)) out += ch;
    else if (byte < 0x80 && TWICE[ch]) out += TWICE[ch];
    else out += `%${HEX(byte)}`;
  }
  return out;
}

function alpha(percent: number): string {
  return HEX(rhu((percent * 255) / 100));
}

function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}

/** A public id as an overlay (l_) names it: folders separated by colons. */
export function overlayId(publicId: string): string {
  return publicId.replaceAll("/", ":");
}

// ---------------------------------------------------------------- geometry

export type Frame = {
  width: number;
  height: number;
  crop_x: number;
  crop_y: number;
  crop_w: number;
  crop_h: number;
  out_w: number;
  out_h: number;
};

function even(value: number): number {
  return Math.max(value - (value % 2), 2);
}

/** The crop rectangle (whole pixels of the rotated media) and the output size. */
export function frame(asset: AssetMeta, spec: EditSpec): Frame {
  if (asset.width <= 0 || asset.height <= 0) throw new TransformError("The media has no dimensions, so it can't be edited.");
  const video = asset.resource_type === "video";
  const [w, h] = spec.rotate === 90 || spec.rotate === 270 ? [asset.height, asset.width] : [asset.width, asset.height];
  let cw = w;
  let ch = h;
  let cx = 0;
  let cy = 0;
  const crop = spec.crop;
  if (crop) {
    let bw: number;
    let bh: number;
    if (crop.aspect === "original") {
      bw = w;
      bh = h;
    } else {
      const [aw, ah] = ASPECTS[crop.aspect];
      if (w * ah > h * aw) {
        bw = (h * aw) / ah;
        bh = h;
      } else {
        bw = w;
        bh = (w * ah) / aw;
      }
    }
    cw = Math.min(Math.max(rhu(bw / crop.zoom), 1), w);
    ch = Math.min(Math.max(rhu(bh / crop.zoom), 1), h);
    if (video) {
      cw = Math.min(even(cw), w);
      ch = Math.min(even(ch), h);
    }
    cx = clamp(rhu(crop.x * w - cw / 2), 0, w - cw);
    cy = clamp(rhu(crop.y * h - ch / 2), 0, h - ch);
  }
  const cap = MAX_WIDTH[asset.resource_type];
  let ow = cw;
  let oh = ch;
  if (cw > cap) {
    ow = cap;
    oh = rhu((cap * ch) / cw);
  }
  if (video) {
    ow = even(ow);
    oh = even(oh);
  }
  return { width: w, height: h, crop_x: cx, crop_y: cy, crop_w: cw, crop_h: ch, out_w: ow, out_h: oh };
}

function geometry(spec: EditSpec, f: Frame): string[] {
  const parts: string[] = [];
  if (spec.rotate) parts.push(`a_${spec.rotate}`);
  if (spec.flip_h) parts.push("a_hflip");
  if (spec.flip_v) parts.push("a_vflip");
  if (f.crop_w !== f.width || f.crop_h !== f.height) parts.push(`c_crop,w_${f.crop_w},h_${f.crop_h},x_${f.crop_x},y_${f.crop_y}`);
  if (f.out_w !== f.crop_w || f.out_h !== f.crop_h) parts.push(`c_scale,w_${f.out_w},h_${f.out_h}`);
  return parts;
}

// ---------------------------------------------------------------- colour

/** The preset's adjustments plus the owner's, clamped; photo-only ones dropped on video. */
export function effectiveAdjustments(spec: EditSpec, kind: MediaKind): Partial<Record<AdjustmentName, number>> {
  const base = spec.preset ? PRESETS[spec.preset] : {};
  const values: Partial<Record<AdjustmentName, number>> = {};
  for (const name of ADJUSTMENT_ORDER) {
    if (kind === "video" && PHOTO_ONLY_ADJUSTMENTS.includes(name)) continue;
    const [low, high] = ADJUSTMENTS[name];
    const value = clamp((base[name] ?? 0) + (spec.adjust?.[name] ?? 0), low, high);
    if (value) values[name] = value;
  }
  return values;
}

function warmth(value: number, f: Frame): string[] {
  const rgb = value > 0 ? WARM_RGB : COOL_RGB;
  const a = HEX(rhu((Math.abs(value) * WARMTH_MAX_ALPHA) / 100));
  return [`l_text:Arial_20:%20,b_rgb:${rgb}${a}`, `c_scale,w_${f.out_w},h_${f.out_h}`, "fl_layer_apply"];
}

function colour(spec: EditSpec, kind: MediaKind, f: Frame): string[] {
  const parts: string[] = [];
  if (kind === "image") {
    if (spec.enhance) parts.push("e_improve");
    if (spec.look) parts.push(`e_art:${spec.look}`);
  }
  const values = effectiveAdjustments(spec, kind);
  for (const name of ADJUSTMENT_ORDER) {
    const value = values[name];
    if (value === undefined) continue;
    if (name === "warmth") parts.push(...warmth(value, f));
    else if (name === "vignette") parts.push(`e_vignette:${value},b_black`);
    else parts.push(`e_${name}:${value}`);
  }
  return parts;
}

// ---------------------------------------------------------------- overlays

function offset(fraction: number, size: number): number {
  return rhu((fraction - 0.5) * size);
}

function placement(x: number, y: number, f: Frame): string {
  const parts = ["fl_layer_apply", "fl_no_overflow", "g_center"];
  const dx = offset(x, f.out_w);
  const dy = offset(y, f.out_h);
  if (dx) parts.push(`x_${dx}`);
  if (dy) parts.push(`y_${dy}`);
  return parts.join(",");
}

function text(layer: TextLayer, f: Frame, timing: boolean): string[] {
  const px = Math.max(rhu(layer.size * f.out_w), 8);
  let style = `${encodeText(FONTS[layer.font])}_${px}`;
  if (layer.bold) style += "_bold";
  if (layer.italic) style += "_italic";
  if (layer.align !== "left") style += `_${layer.align}`;
  const params = [`l_text:${style}:${encodeText(layer.text)}`, `co_rgb:${layer.color.slice(1).toUpperCase()}`];
  if (layer.background != null) {
    const box = `rgb:${layer.background.slice(1).toUpperCase()}${alpha(layer.background_opacity)}`;
    params.push(`b_${box}`);
    params.push(`bo_${Math.max(rhu(px * TEXT_PADDING), 1)}px_solid_${box}`);
  }
  params.push("c_limit", `w_${Math.max(rhu(f.out_w * TEXT_MAX_WIDTH), 1)}`);
  let apply = placement(layer.x, layer.y, f);
  if (timing) {
    if (layer.start_s != null) apply += `,so_${fmt(layer.start_s)}`;
    if (layer.end_s != null) apply += `,eo_${fmt(layer.end_s)}`;
  }
  return [params.join(","), apply];
}

function visibleAt(layer: TextLayer, at: number): boolean {
  if (layer.start_s != null && at < layer.start_s) return false;
  return !(layer.end_s != null && at >= layer.end_s);
}

function logo(spec: EditSpec, f: Frame, logoPublicId: string | null | undefined): string[] {
  if (!spec.logo) return [];
  if (!logoPublicId) throw new TransformError("The logo's file is missing.");
  const params = [`l_${overlayId(logoPublicId)}`, "c_scale", `w_${Math.max(rhu(spec.logo.width * f.out_w), 1)}`];
  if (spec.logo.opacity < 100) params.push(`o_${spec.logo.opacity}`);
  return [params.join(","), placement(spec.logo.x, spec.logo.y, f)];
}

// ---------------------------------------------------------------- builds

function url(asset: AssetMeta, transformation: string, ext: string): string {
  return `${DELIVERY_BASE}/${asset.cloud_name}/${asset.resource_type}/upload/${transformation}/${asset.public_id}.${ext}`;
}

/** Seconds of the trimmed clip, before speed (null when the length isn't known). */
export function clipLength(asset: AssetMeta, spec: EditSpec): number | null {
  if (spec.trim) {
    let end = spec.trim.end_s;
    if (asset.duration_s != null) end = Math.min(end, asset.duration_s);
    return Math.max(end - spec.trim.start_s, 0);
  }
  return asset.duration_s ?? null;
}

export type BuildOptions = { logoPublicId?: string | null };

/** The rendered file: the edited photo (on the fly) or video (rendered by the API). */
export function build(asset: AssetMeta, input: PartialEditSpec, options: BuildOptions = {}): Built {
  const spec = normalizeSpec(input);
  const f = frame(asset, spec);
  const kind = asset.resource_type;
  const parts: string[] = [];
  if (kind === "video" && spec.trim) parts.push(`so_${fmt(spec.trim.start_s)},eo_${fmt(spec.trim.end_s)}`);
  parts.push(...geometry(spec, f), ...colour(spec, kind, f));
  for (const layer of spec.texts ?? []) parts.push(...text(layer, f, kind === "video"));
  parts.push(...logo(spec, f, options.logoPublicId));
  let duration: number | null = null;
  let ext: Built["format"] = "jpg";
  if (kind === "video") {
    const accelerate = SPEEDS[String(spec.speed)];
    if (accelerate) parts.push(`e_accelerate:${accelerate}`);
    if (spec.fade_in_s > 0) parts.push(`e_fade:${rhu(spec.fade_in_s * 1000)}`);
    if (spec.fade_out_s > 0) parts.push(`e_fade:-${rhu(spec.fade_out_s * 1000)}`);
    if (spec.mute) parts.push("e_volume:mute");
    parts.push(VIDEO_DELIVERY);
    const length = clipLength(asset, spec);
    duration = length == null ? null : rhu((length / spec.speed) * 100) / 100;
    ext = "mp4";
  } else {
    parts.push(IMAGE_DELIVERY);
  }
  const transformation = parts.join("/");
  return { kind, transformation, format: ext, url: url(asset, transformation, ext), width: f.out_w, height: f.out_h, duration_s: duration };
}

export type StillOptions = BuildOptions & { atS?: number; maxWidth?: number | null };

/**
 * A JPEG preview. For a video: the frame ``atS`` seconds into the trimmed clip with the same crop,
 * colour, logo and the text showing at that moment (not speed, fades or sound); also the Reel
 * cover. For a photo: the edited photo. ``maxWidth`` scales it down (never up).
 */
export function still(asset: AssetMeta, input: PartialEditSpec, options: StillOptions = {}): Built {
  const spec = normalizeSpec(input);
  const at = options.atS ?? 0;
  const f = frame(asset, spec);
  const kind = asset.resource_type;
  const parts: string[] = [];
  if (kind === "video") parts.push(`so_${fmt((spec.trim ? spec.trim.start_s : 0) + at)}`);
  parts.push(...geometry(spec, f), ...colour(spec, kind, f));
  for (const layer of spec.texts ?? []) {
    if (kind === "image" || visibleAt(layer, at)) parts.push(...text(layer, f, false));
  }
  parts.push(...logo(spec, f, options.logoPublicId));
  let width = f.out_w;
  let height = f.out_h;
  if (options.maxWidth != null && options.maxWidth < width) {
    height = rhu((options.maxWidth * height) / width);
    width = options.maxWidth;
    parts.push(`c_scale,w_${width}`);
  }
  parts.push(IMAGE_DELIVERY);
  const transformation = parts.join("/");
  return { kind: "image", transformation, format: "jpg", url: url(asset, transformation, "jpg"), width, height, duration_s: null };
}

/** The Reel cover (Instagram's cover_url): the still at ``cover_s``; null without one. */
export function cover(asset: AssetMeta, input: PartialEditSpec, options: BuildOptions = {}): Built | null {
  const spec = normalizeSpec(input);
  if (asset.resource_type !== "video" || spec.cover_s == null) return null;
  return still(asset, spec, { ...options, atS: spec.cover_s });
}
