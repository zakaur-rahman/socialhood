// Generates the app icons (TR-FE-09) from the brand mark: the shell-gradient tile (UX-SH-01,
// #3352CC to #1C2D70 at 135°) with a white chat bubble. No dependencies: pixels are computed
// with 4×4 supersampling and written as PNG with node:zlib.
//
//   node scripts/generate-icons.mjs
//
// Writes public/icons/icon-192.png, icon-512.png (rounded tile, transparent corners),
// icon-maskable-512.png (full bleed, mark inside the 80% safe zone), badge-72.png (white
// mark on transparent, for Android's status bar) and src/app/apple-icon.png (180, full bleed:
// iOS rounds the corners itself).
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const FROM = [0x33, 0x52, 0xcc];
const TO = [0x1c, 0x2d, 0x70];

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

/** The chat bubble with three dots cut out, scaled around the centre. */
function inMark(x, y, scale) {
  const u = 0.5 + (x - 0.5) / scale;
  const v = 0.5 + (y - 0.5) / scale;
  const body = inRoundedRect(u, v, 0.2, 0.24, 0.8, 0.7, 0.13);
  const tail = inTriangle(u, v, [0.3, 0.64], [0.46, 0.66], [0.26, 0.82]);
  if (!body && !tail) return false;
  for (const dx of [0.36, 0.5, 0.64]) {
    if ((u - dx) ** 2 + (v - 0.47) ** 2 <= 0.048 ** 2) return false;
  }
  return true;
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

/** The tile: gradient with the white mark; `rounded` leaves the corners transparent. */
function tile({ rounded, markScale }) {
  return (x, y) => {
    if (rounded && !inRoundedRect(x, y, 0, 0, 1, 1, 0.22)) return [0, 0, 0, 0];
    if (inMark(x, y, markScale)) return [255, 255, 255, 1];
    return [...gradient(x, y), 1];
  };
}

const badge = (x, y) => (inMark(x, y, 1.25) ? [255, 255, 255, 1] : [0, 0, 0, 0]);

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
