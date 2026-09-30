/**
 * The media editor's edit spec, version 1 (P7b: FR-PUB-20…27, TR-MED-04).
 *
 * The twin of apps/api/src/socialhood/media/editor/spec.py: the types come from the contract, and
 * every constant and default here must equal the API's. The golden fixtures
 * (packages/editor-fixtures/transform-cases.json) carry the API's constants and run both builders,
 * so a difference fails transform.test.ts.
 *
 * The API validates a spec (ranges, 5 text layers, 150 characters, no emoji outside the Basic
 * Multilingual Plane, photo-only and video-only tools); the builder here assumes a valid one and
 * the editor should never produce anything else.
 */
import type { components } from "@socialhood/api-client";

type Schemas = components["schemas"];

export type EditSpec = Schemas["EditSpec"];
export type Crop = Schemas["Crop"];
export type Adjustments = Schemas["Adjustments"];
export type TextLayer = Schemas["TextLayer"];
export type Logo = Schemas["Logo"];
export type Trim = Schemas["Trim"];
export type AspectName = Crop["aspect"];
export type FontName = TextLayer["font"];
export type LookName = NonNullable<EditSpec["look"]>;
export type PresetName = NonNullable<EditSpec["preset"]>;
export type AdjustmentName = keyof Adjustments;
export type Speed = EditSpec["speed"];
export type MediaKind = "image" | "video";

/** A spec as stored or typed by hand: any field may be left out, as the API allows. */
export type PartialEditSpec = Partial<Omit<EditSpec, "crop" | "adjust" | "texts" | "logo" | "trim">> & {
  crop?: Partial<Crop> | null;
  adjust?: Partial<Adjustments>;
  texts?: (Partial<TextLayer> & { text: string })[];
  logo?: (Partial<Logo> & { asset_id: string }) | null;
  trim?: (Partial<Trim> & { end_s: number }) | null;
};

export const SPEC_VERSION = 1;

/** width:height as whole numbers, so crops compare exactly. */
export const ASPECTS: Record<Exclude<AspectName, "original">, [number, number]> = {
  "1:1": [1, 1],
  "4:5": [4, 5],
  "1.91:1": [191, 100],
  "9:16": [9, 16],
};

/** Output width caps: photos 1440 px (Instagram's maximum), video renders 1080 px. */
export const MAX_WIDTH: Record<MediaKind, number> = { image: 1440, video: 1080 };

/** Google fonts Cloudinary renders (the spike's list). */
export const FONTS: Record<FontName, string> = {
  poppins: "Poppins",
  montserrat: "Montserrat",
  playfair: "Playfair Display",
  pacifico: "Pacifico",
  anton: "Anton",
  marker: "Permanent Marker",
};

/** Cloudinary's artistic filters (e_art), photos only. */
export const LOOKS: readonly LookName[] = [
  "al_dente",
  "athena",
  "audrey",
  "aurora",
  "eucalyptus",
  "fes",
  "frost",
  "hairspray",
  "hokusai",
  "incognito",
  "linen",
  "peacock",
  "primavera",
  "quartz",
  "red_rock",
  "refresh",
  "sizzle",
  "sonnet",
  "ukulele",
  "zorro",
];

/** [min, max] of each adjustment; 0 is "no change" for all of them. */
export const ADJUSTMENTS: Record<AdjustmentName, [number, number]> = {
  brightness: [-99, 100],
  contrast: [-100, 100],
  saturation: [-100, 100],
  gamma: [-50, 100],
  vibrance: [-100, 100],
  warmth: [-100, 100],
  vignette: [0, 100],
  sharpen: [0, 400],
};

/** Adjustments video ignores (Cloudinary applies them to photos only). */
export const PHOTO_ONLY_ADJUSTMENTS: readonly AdjustmentName[] = ["sharpen", "vibrance"];

/** The order adjustments apply in, one component each. */
export const ADJUSTMENT_ORDER: readonly AdjustmentName[] = [
  "brightness",
  "contrast",
  "saturation",
  "gamma",
  "vibrance",
  "warmth",
  "vignette",
  "sharpen",
];

export const WARM_RGB = "FF8C00";
export const COOL_RGB = "0064FF";
export const WARMTH_MAX_ALPHA = 64;

/** Filters that work on photos and video alike; the owner's adjustments add to them. */
export const PRESETS: Record<PresetName, Partial<Adjustments>> = {
  vivid: { contrast: 15, saturation: 35 },
  warm: { saturation: 10, warmth: 40 },
  cool: { brightness: 5, warmth: -40 },
  mono: { contrast: 20, saturation: -100 },
  fade: { brightness: 10, contrast: -25, saturation: -20 },
  noir: { contrast: 45, saturation: -100, vignette: 40 },
  golden: { contrast: 10, gamma: 10, warmth: 55 },
  dramatic: { contrast: 40, saturation: -10, vignette: 50 },
  bright: { brightness: 20, contrast: -10 },
  retro: { contrast: -10, saturation: -30, warmth: 30, vignette: 30 },
};

/** e_accelerate percentages, keyed by the speed as written ("0.5", "1", "1.5", "2"). */
export const SPEEDS: Record<string, number> = { "0.5": -50, "1": 0, "1.5": 50, "2": 100 };

export const TEXT_MAX_LAYERS = 5;
export const TEXT_MAX_CHARS = 150;
export const TEXT_MAX_LINES = 5;
export const TEXT_SIZE_RANGE: [number, number] = [0.02, 0.2];
/** A text box wider than this fraction of the output (a long line) is scaled down to it. */
export const TEXT_MAX_WIDTH = 0.9;
/** The background box's padding, as a fraction of the font size. */
export const TEXT_PADDING = 0.3;
export const LOGO_WIDTH_RANGE: [number, number] = [0.05, 0.5];
export const CROP_MAX_ZOOM = 4;
export const FADE_MAX_S = 3;
export const TRIM_MIN_S = 1;

/** The constants as the golden fixtures carry them (compared in transform.test.ts). */
export const EDITOR_CONSTANTS = {
  version: SPEC_VERSION,
  aspects: ASPECTS,
  max_width: MAX_WIDTH,
  fonts: FONTS,
  looks: LOOKS,
  adjustments: ADJUSTMENTS,
  adjustment_order: ADJUSTMENT_ORDER,
  photo_only_adjustments: PHOTO_ONLY_ADJUSTMENTS,
  presets: PRESETS,
  speeds: SPEEDS,
  warm_rgb: WARM_RGB,
  cool_rgb: COOL_RGB,
  warmth_max_alpha: WARMTH_MAX_ALPHA,
  text_max_layers: TEXT_MAX_LAYERS,
  text_max_chars: TEXT_MAX_CHARS,
  text_max_lines: TEXT_MAX_LINES,
  text_size_range: TEXT_SIZE_RANGE,
  text_max_width: TEXT_MAX_WIDTH,
  text_padding: TEXT_PADDING,
  logo_width_range: LOGO_WIDTH_RANGE,
  crop_max_zoom: CROP_MAX_ZOOM,
  fade_max_s: FADE_MAX_S,
  trim_min_s: TRIM_MIN_S,
};

// ---------------------------------------------------------------- defaults (the API's)

export const DEFAULT_ADJUSTMENTS: Adjustments = {
  brightness: 0,
  contrast: 0,
  saturation: 0,
  gamma: 0,
  vibrance: 0,
  warmth: 0,
  vignette: 0,
  sharpen: 0,
};

/** An empty edit: renders the media as Instagram needs it and nothing more. */
export function emptySpec(): EditSpec {
  return {
    v: 1,
    rotate: 0,
    flip_h: false,
    flip_v: false,
    crop: null,
    preset: null,
    adjust: { ...DEFAULT_ADJUSTMENTS },
    look: null,
    enhance: false,
    texts: [],
    logo: null,
    trim: null,
    speed: 1,
    fade_in_s: 0,
    fade_out_s: 0,
    mute: false,
    cover_s: null,
  };
}

export function textLayer(values: Partial<TextLayer> & { text: string }): TextLayer {
  return {
    font: "poppins",
    size: 0.06,
    color: "#FFFFFF",
    bold: false,
    italic: false,
    align: "center",
    background: null,
    background_opacity: 60,
    x: 0.5,
    y: 0.5,
    start_s: null,
    end_s: null,
    ...values,
  };
}

/** Every field filled with the API's defaults, as the API returns a spec. */
export function normalizeSpec(input: PartialEditSpec): EditSpec {
  const base = emptySpec();
  return {
    ...base,
    ...input,
    v: 1,
    crop: input.crop ? { aspect: "original", zoom: 1, x: 0.5, y: 0.5, ...input.crop } : null,
    adjust: { ...DEFAULT_ADJUSTMENTS, ...input.adjust },
    texts: (input.texts ?? []).map(textLayer),
    logo: input.logo ? { width: 0.2, opacity: 100, x: 0.88, y: 0.92, ...input.logo } : null,
    trim: input.trim ? { start_s: 0, ...input.trim } : null,
    preset: input.preset ?? null,
    look: input.look ?? null,
    cover_s: input.cover_s ?? null,
  };
}

/** The look of a photo: what "Apply this look to all photos" copies (FR-PUB-26). */
export function lookOf(spec: EditSpec): Pick<EditSpec, "preset" | "adjust" | "look" | "enhance"> {
  return { preset: spec.preset ?? null, adjust: { ...DEFAULT_ADJUSTMENTS, ...spec.adjust }, look: spec.look ?? null, enhance: spec.enhance };
}

/** ``target`` with ``source``'s look; its crop, text, logo and the rest stay its own. */
export function withLook(target: EditSpec, source: EditSpec): EditSpec {
  return { ...target, ...lookOf(source) };
}
