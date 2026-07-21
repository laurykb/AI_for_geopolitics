/** Texture de la planète (spec théâtre-globe §1) — palette naturelle assombrie
 * et peintre équirectangulaire. Env node sans canvas : un contexte 2D factice
 * enregistre les opérations, d3-geo dessine dedans comme dans le vrai. */

import { describe, expect, it } from "vitest";

import { uTint } from "@/lib/stage";
import { WORLD_FEATURES } from "@/lib/world";
import { createGlobePainter, landColorFor, TEX_H, TEX_W } from "./texture";
import { summitFeatures } from "./picking";

/** Contexte 2D minimal : enregistre styles posés et méthodes appelées. */
function recordingCtx() {
  const ops: [string, unknown?][] = [];
  const push = (name: string, v?: unknown) => ops.push(v === undefined ? [name] : [name, v]);
  const ctx = {
    ops,
    set fillStyle(v: unknown) {
      push("fillStyle", v);
    },
    set strokeStyle(v: unknown) {
      push("strokeStyle", v);
    },
    set shadowColor(v: unknown) {
      push("shadowColor", v);
    },
    set shadowBlur(_v: unknown) {},
    set lineWidth(_v: unknown) {},
    createLinearGradient: () => ({ addColorStop: () => undefined }),
    fillRect: (...a: unknown[]) => push("fillRect", a),
    beginPath: () => push("beginPath"),
    moveTo: () => undefined,
    lineTo: () => undefined,
    arc: () => undefined,
    closePath: () => undefined,
    fill: () => push("fill"),
    stroke: () => push("stroke"),
    save: () => push("save"),
    restore: () => push("restore"),
  };
  return ctx as unknown as CanvasRenderingContext2D & { ops: [string, unknown?][] };
}

describe("landColorFor (palette naturelle éteinte, variée par ISO)", () => {
  it("peint glaces, déserts, boréal et tempéré dans leurs gammes", () => {
    expect(landColorFor("304")).toBe(landColorFor("010")); // Groenland = Antarctique = glace
    expect(landColorFor("012")).toMatch(/^#[0-9a-f]{6}$/i); // Algérie : sable
    expect(landColorFor("012")).not.toBe(landColorFor("250")); // sable ≠ vert tempéré
    expect(landColorFor("124")).not.toBe(landColorFor("012")); // boréal ≠ sable
  });

  it("est déterministe (même ISO → même couleur)", () => {
    expect(landColorFor("818")).toBe(landColorFor("818"));
    expect(landColorFor("250")).toBe(landColorFor("250"));
  });
});

describe("createGlobePainter (entrées → opérations de dessin)", () => {
  const feats = summitFeatures(["france", "usa"], WORLD_FEATURES);
  const summit = feats.map((f, i) => ({ ...f, u: i === 0 ? 0.61 : 0.58 }));

  it("pose l'océan sur toute la texture puis remplit des terres", () => {
    const ctx = recordingCtx();
    createGlobePainter({ ctx, features: WORLD_FEATURES, width: TEX_W, height: TEX_H }).paint(
      summit,
      null,
    );
    const firstRect = ctx.ops.find(([op]) => op === "fillRect");
    expect(firstRect?.[1]).toEqual([0, 0, TEX_W, TEX_H]);
    expect(ctx.ops.filter(([op]) => op === "fill").length).toBeGreaterThan(50);
  });

  it("remplit l'orateur en ambre, liseré uTint pour les autres", () => {
    const ctx = recordingCtx();
    createGlobePainter({ ctx, features: WORLD_FEATURES, width: TEX_W, height: TEX_H }).paint(
      summit,
      "france",
    );
    const styles = ctx.ops.filter(([op]) => op === "fillStyle").map(([, v]) => v);
    expect(styles).toContain("#ffc14d"); // la France parle
    const strokes = ctx.ops.filter(([op]) => op === "strokeStyle").map(([, v]) => v);
    expect(strokes).toContain(uTint(0.58)); // liseré des États-Unis à leur teinte U
  });

  it("sans orateur, aucun remplissage ambre", () => {
    const ctx = recordingCtx();
    createGlobePainter({ ctx, features: WORLD_FEATURES, width: TEX_W, height: TEX_H }).paint(
      summit,
      null,
    );
    const styles = ctx.ops.filter(([op]) => op === "fillStyle").map(([, v]) => v);
    expect(styles).not.toContain("#ffc14d");
  });
});
