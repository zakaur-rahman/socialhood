// Generates the app icons (TR-FE-09) from the brand mark: the shell-gradient tile (UX-SH-01,
// shell-1 to shell-2 at 135°, read from src/styles/tokens.generated.json) with a white chat
// bubble holding three brand-deep bars (C-140). No dependencies: pixels are computed with 4×4
// supersampling and written as PNG with node:zlib.
//
//   node scripts/generate-icons.mjs
//
// Writes public/icons/icon-192.png, icon-512.png (rounded tile, transparent corners),
// icon-maskable-512.png (full bleed, mark inside the 80% safe zone), badge-72.png (white
// mark on transparent, for Android's status bar), src/app/apple-icon.png (180, full bleed:
// iOS rounds the corners itself) and src/app/favicon.ico (16, 32 and 48, PNG inside).
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

// The colours come from the generated tokens (globals.css is the only place they are written), so
// the icons follow a change to shell-1, shell-2 or fg after `pnpm tokens`.
const { colors } = JSON.parse(readFileSync(join(root, "src", "styles", "tokens.generated.json"), "utf8"));

/** `#RRGGBB` as [r, g, b]. */
function hex(name) {
  const match = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(colors[name]);
  if (!match) throw new Error(`Token ${name} is not a #RRGGBB colour: ${colors[name]}`);
  return match.slice(1).map((byte) => parseInt(byte, 16));
}

const FROM = hex("shell-1");
const TO = hex("shell-2");
const MARK = hex("fg");
const BARS = hex("brand-deep");

// ---- PNG

const CRC_TABLE = new Uint32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(bytes) {
  let c = 0xffffffff;
  for (const byte of bytes) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const out = Buffer.alloc(12 + data.length);
  out.writeUInt32BE(data.length, 0);
  out.write(type, 4, "ascii");
  data.copy(out, 8);
  out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length);
  return out;
}

function png(size, rgba) {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header[8] = 8; // bit depth
  header[9] = 6; // RGBA
  const raw = Buffer.alloc((size * 4 + 1) * size);
  for (let y = 0; y < size; y += 1) {
    raw[y * (size * 4 + 1)] = 0; // filter: none
    rgba.copy(raw, y * (size * 4 + 1) + 1, y * size * 4, (y + 1) * size * 4);
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

// ---- shapes, in unit coordinates (0..1 across the icon)

function inRoundedRect(x, y, left, top, right, bottom, radius) {
  if (x < left || x > right || y < top || y > bottom) return false;
  const cx = Math.min(Math.max(x, left + radius), right - radius);
  const cy = Math.min(Math.max(y, top + radius), bottom - radius);
  return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2;
}

function inTriangle(x, y, [ax, ay], [bx, by], [cx, cy]) {
  const d1 = (x - bx) * (ay - by) - (ax - bx) * (y - by);
  const d2 = (x - cx) * (by - cy) - (bx - cx) * (y - cy);
  const d3 = (x - ax) * (cy - ay) - (cx - ax) * (y - ay);
  const negative = d1 < 0 || d2 < 0 || d3 < 0;
  const positive = d1 > 0 || d2 > 0 || d3 > 0;
  return !(negative && positive);
}

// The "amp bubble" (C-140), the same shape as LogoMark in components/marketing/primitives.tsx: a
// chat bubble on a 64-unit tile holding three rising bars, given here as [x, y, height] in units.
const UNIT = 1 / 64;
const LOGO_BARS = [
  [21.5, 30, 7],
  [29.5, 25, 12],
  [37.5, 19, 18],
];

/** What the mark covers at (x, y), scaled around the centre: "bubble", "bar" or null. */
function markAt(x, y, scale) {
  const u = 0.5 + (x - 0.5) / scale;
  const v = 0.5 + (y - 0.5) / scale;
  const body = inRoundedRect(u, v, 12 * UNIT, 13 * UNIT, 52 * UNIT, 43 * UNIT, 8 * UNIT);
  const tail = inTriangle(u, v, [19 * UNIT, 42 * UNIT], [29 * UNIT, 42 * UNIT], [19 * UNIT, 51 * UNIT]);
  if (!body && !tail) return null;
  for (const [bx, by, height] of LOGO_BARS) {
    if (inRoundedRect(u, v, bx * UNIT, by * UNIT, (bx + 5) * UNIT, (by + height) * UNIT, 2.5 * UNIT)) return "bar";
  }
  return "bubble";
}

// ---- icons

const SAMPLES = 4;

function render(size, pixel) {
  const out = Buffer.alloc(size * size * 4);
  for (let py = 0; py < size; py += 1) {
    for (let px = 0; px < size; px += 1) {
      let r = 0;
      let g = 0;
      let b = 0;
      let a = 0;
      for (let sy = 0; sy < SAMPLES; sy += 1) {
        for (let sx = 0; sx < SAMPLES; sx += 1) {
          const [cr, cg, cb, ca] = pixel((px + (sx + 0.5) / SAMPLES) / size, (py + (sy + 0.5) / SAMPLES) / size);
          r += cr * ca;
          g += cg * ca;
          b += cb * ca;
          a += ca;
        }
      }
      const i = (py * size + px) * 4;
      out[i] = a ? Math.round(r / a) : 0;
      out[i + 1] = a ? Math.round(g / a) : 0;
      out[i + 2] = a ? Math.round(b / a) : 0;
      out[i + 3] = Math.round((a / (SAMPLES * SAMPLES)) * 255);
    }
  }
  return png(size, out);
}

function gradient(x, y) {
  const t = Math.min(1, Math.max(0, (x + y) / 2));
  return FROM.map((from, i) => from + (TO[i] - from) * t);
}

/** The tile: gradient with the white bubble and brand-deep bars; `rounded` leaves the corners transparent. */
function tile({ rounded, markScale }) {
  return (x, y) => {
    if (rounded && !inRoundedRect(x, y, 0, 0, 1, 1, 0.22)) return [0, 0, 0, 0];
    const part = markAt(x, y, markScale);
    if (part === "bar") return [...BARS, 1];
    if (part === "bubble") return [...MARK, 1];
    return [...gradient(x, y), 1];
  };
}

// The badge is one colour (Android tints it), so the bars are cut out of the bubble.
const badge = (x, y) => (markAt(x, y, 1.25) === "bubble" ? [...MARK, 1] : [0, 0, 0, 0]);

/** An .ico holding PNG images (every current browser reads them), one per size. */
function ico(images) {
  const header = Buffer.alloc(6 + images.length * 16);
  header.writeUInt16LE(1, 2); // type: icon
  header.writeUInt16LE(images.length, 4);
  let offset = header.length;
  images.forEach(({ size, data }, i) => {
    const entry = 6 + i * 16;
    header[entry] = size;
    header[entry + 1] = size;
    header.writeUInt16LE(1, entry + 4); // colour planes
    header.writeUInt16LE(32, entry + 6); // bits per pixel
    header.writeUInt32LE(data.length, entry + 8);
    header.writeUInt32LE(offset, entry + 12);
    offset += data.length;
  });
  return Buffer.concat([header, ...images.map(({ data }) => data)]);
}

const outputs = [
  ["public/icons/icon-192.png", 192, tile({ rounded: true, markScale: 1 })],
  ["public/icons/icon-512.png", 512, tile({ rounded: true, markScale: 1 })],
  ["public/icons/icon-maskable-512.png", 512, tile({ rounded: false, markScale: 0.8 })],
  ["public/icons/badge-72.png", 72, badge],
  ["src/app/apple-icon.png", 180, tile({ rounded: false, markScale: 0.9 })],
];

for (const [path, size, pixel] of outputs) {
  const file = join(root, path);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, render(size, pixel));
  console.log(`wrote ${path} (${size}×${size})`);
}

// The favicon: the rounded tile at the sizes browsers ask for (tab, taskbar, shortcut).
const favicon = [16, 32, 48].map((size) => ({ size, data: render(size, tile({ rounded: true, markScale: 1.08 })) }));
writeFileSync(join(root, "src/app/favicon.ico"), ico(favicon));
console.log("wrote src/app/favicon.ico (16, 32, 48)");
