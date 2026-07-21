/** Texture de la planète (spec théâtre-globe §1) — peinture équirectangulaire.
 *
 * Une vraie géographie, palette assombrie : océan quasi-nuit + grille de
 * points tech, terres en verts/sables/glaces éteints (variés par hash d'ISO),
 * côtes lumineuses (la signature holo), graticule discret. Les pays du sommet
 * portent un liseré à leur teinte U (`uTint`, échelle fixe du jeu) ; l'orateur
 * se remplit d'ambre. Pur côté logique : le peintre reçoit son contexte 2D —
 * les tests lui donnent un contexte factice qui enregistre les opérations. */

import { geoEquirectangular, geoGraticule10, geoPath } from "d3-geo";

import { uTint } from "@/lib/stage";
import type { GlobeFeature } from "./picking";

export const TEX_W = 4096;
export const TEX_H = 2048;

/** Remplissage de l'orateur (l'ambre du théâtre) + son trait de côte clair. */
export const SPEAKER_FILL = "#ffc14d";
const SPEAKER_STROKE = "#ffe9c2";

// Ceintures climatiques par ISO numérique (fond world-atlas) — déclaratif.
const ICE = new Set(["304", "010"]); // Groenland, Antarctique
const DESERT = new Set([
  "012", "434", "818", "148", "562", "466", "478", "732", "729", "682", "368",
  "364", "760", "400", "887", "512", "784", "414", "634", "048", "036", "398",
  "795", "860", "004", "586", "496", "516", "072", "504", "788", "262", "232",
  "706",
]);
const BOREAL = new Set(["643", "124", "352", "578", "752", "246"]);

const GREENS = ["#2c4a31", "#315339", "#294630", "#365a3f", "#243d27", "#3a5f45", "#2f5136"];
const SANDS = ["#6e5a38", "#7a6440", "#66522f", "#5f4b2b"];
const BOREALS = ["#25402c", "#203828"];
const ICE_COLOR = "#a9bccd";

/** Couleur de terre d'un pays — déterministe, variée par hash de l'ISO. */
export function landColorFor(isoId: string): string {
  const h = (parseInt(isoId, 10) || 7) * 37;
  if (ICE.has(isoId)) return ICE_COLOR;
  if (DESERT.has(isoId)) return SANDS[h % SANDS.length];
  if (BOREAL.has(isoId)) return BOREALS[h % BOREALS.length];
  return GREENS[h % GREENS.length];
}

export type SummitTint = { slug: string; feat: GlobeFeature | undefined; u: number };

export type GlobePainterInput = {
  ctx: CanvasRenderingContext2D;
  features: GlobeFeature[];
  width?: number;
  height?: number;
};

/** Peintre du globe : projection et chemin construits une fois, `paint`
 * rejoué seulement aux changements d'état (orateur, teintes U). */
export function createGlobePainter({
  ctx,
  features,
  width = TEX_W,
  height = TEX_H,
}: GlobePainterInput) {
  const proj = geoEquirectangular().fitExtent(
    [
      [0, 0],
      [width, height],
    ],
    { type: "Sphere" },
  );
  const path = geoPath(proj, ctx);

  function paint(summit: SummitTint[], speaking: string | null): void {
    // Océan : dégradé nuit + grille de points tech (planète futuriste).
    const sea = ctx.createLinearGradient(0, 0, 0, height);
    sea.addColorStop(0, "#050e1d");
    sea.addColorStop(0.5, "#0a2138");
    sea.addColorStop(1, "#050e1d");
    ctx.fillStyle = sea;
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = "rgba(120,180,255,.05)";
    for (let y = 24; y < height; y += 48)
      for (let x = 24; x < width; x += 48) ctx.fillRect(x, y, 2.2, 2.2);
    ctx.strokeStyle = "rgba(120,170,240,.055)";
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    path(geoGraticule10());
    ctx.stroke();
    // Côtes lumineuses — la signature holo, conservée.
    ctx.save();
    ctx.shadowColor = "rgba(96,175,255,.5)";
    ctx.shadowBlur = 12;
    ctx.strokeStyle = "rgba(150,205,255,.5)";
    ctx.lineWidth = 2;
    for (const f of features) {
      ctx.beginPath();
      path(f);
      ctx.stroke();
    }
    ctx.restore();
    // Terres naturelles assombries.
    for (const f of features) {
      ctx.beginPath();
      path(f);
      ctx.fillStyle = landColorFor(String(f.id));
      ctx.fill();
      ctx.strokeStyle = "rgba(130,180,240,.16)";
      ctx.lineWidth = 0.8;
      ctx.stroke();
    }
    // Pays du sommet : liseré à leur teinte U ; l'orateur se remplit d'ambre.
    for (const { slug, feat, u } of summit) {
      if (!feat) continue;
      ctx.beginPath();
      path(feat);
      if (slug === speaking) {
        ctx.save();
        ctx.shadowColor = "rgba(255,193,77,.95)";
        ctx.shadowBlur = 48;
        ctx.fillStyle = SPEAKER_FILL;
        ctx.fill();
        ctx.restore();
        ctx.strokeStyle = SPEAKER_STROKE;
        ctx.lineWidth = 3.4;
        ctx.stroke();
      } else {
        const c = uTint(u);
        ctx.save();
        ctx.shadowColor = c;
        ctx.shadowBlur = 22;
        ctx.strokeStyle = c;
        ctx.lineWidth = 4.4;
        ctx.stroke();
        ctx.restore();
        ctx.strokeStyle = "rgba(255,255,255,.7)";
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }
    }
  }

  return { paint };
}
