// scripts/downsample-textures.mjs
import sharp from "sharp";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const SRC = resolve("nasa_texture");
const OUT = resolve("web/public/textures");
// La carte JOUR porte le détail regardé de près (gros plans, carte dépliée) → 8K haute
// qualité ; le reste (nuit/nuages/lune/étoiles) tient largement en 2K. [w, quality] par job.
const JOBS = [
  ["8k_earth_daymap.jpg", "earth-day.jpg", 8192, 92],
  ["8k_earth_nightmap.jpg", "earth-night.jpg", 2048, 86],
  ["8k_earth_clouds.jpg", "earth-clouds.jpg", 2048, 86],
  ["8k_moon.jpg", "moon.jpg", 2048, 86],
  ["8k_stars.jpg", "stars.jpg", 2048, 86],
];
await mkdir(OUT, { recursive: true });
for (const [src, out, w, q] of JOBS) {
  await sharp(resolve(SRC, src))
    .resize({ width: w, height: w / 2, fit: "fill" })
    .jpeg({ quality: q, mozjpeg: true })
    .toFile(resolve(OUT, out));
  console.log(`✓ ${out} (${w}×${w / 2}, q${q})`);
}
