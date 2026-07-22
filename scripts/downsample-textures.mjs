// scripts/downsample-textures.mjs
import sharp from "sharp";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const SRC = resolve("nasa_texture");
const OUT = resolve("web/public/textures");
const JOBS = [
  ["8k_earth_daymap.jpg", "earth-day.jpg", 4096],
  ["8k_earth_nightmap.jpg", "earth-night.jpg", 2048],
  ["8k_earth_clouds.jpg", "earth-clouds.jpg", 2048],
  ["8k_moon.jpg", "moon.jpg", 2048],
  ["8k_stars.jpg", "stars.jpg", 2048],
];
await mkdir(OUT, { recursive: true });
for (const [src, out, w] of JOBS) {
  await sharp(resolve(SRC, src))
    .resize({ width: w, height: w / 2, fit: "fill" })
    .jpeg({ quality: 86, mozjpeg: true })
    .toFile(resolve(OUT, out));
  console.log(`✓ ${out} (${w}×${w / 2})`);
}
