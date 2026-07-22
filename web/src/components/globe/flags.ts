/** Drapeaux canvas simplifiés des 33 pays du roster (théâtre-globe, spec §2).
 *
 * Deux moitiés : des SPECS déclaratives pures (testables au vitest, sans canvas)
 * et un peintre `paintFlag` qui les consomme au runtime sur un contexte 2D
 * (torse des délégués en 3D, marqueurs plantés en 2D). Un pays inventé retombe
 * sur un aplat à sa teinte — même règle de repli que `speakerMeta`.
 */

export type Emblem =
  | { kind: "disc"; color: string; r?: number }
  | { kind: "star"; color: string; r?: number }
  | { kind: "crescent"; color: string }
  | { kind: "disc-crescent"; disc: string; mark: string }
  | { kind: "disc-star"; disc: string; star: string }
  | { kind: "diamond"; color: string }
  | { kind: "maple"; color: string }
  | { kind: "square"; color: string }
  | { kind: "bars"; color: string }
  | { kind: "taeguk" }
  | { kind: "hoist-triangle"; color: string }
  | { kind: "hoist-bar"; color: string };

export type FlagSpec =
  | { kind: "bands"; dir: "h" | "v"; colors: string[]; emblem?: Emblem }
  | { kind: "field"; color: string; emblem?: Emblem }
  | { kind: "canton-stripes"; stripes: [string, string]; canton: string; starColor: string }
  | { kind: "union-jack" };

/** Palette volontairement désaturée (nuit du théâtre) mais reconnaissable. */
export const FLAG_SPECS: Record<string, FlagSpec> = {
  south_africa: {
    kind: "bands",
    dir: "h",
    colors: ["#c25050", "#f5f5f5", "#2c5aa8"],
    emblem: { kind: "hoist-triangle", color: "#3f7d54" },
  },
  algeria: {
    kind: "bands",
    dir: "v",
    colors: ["#3f7d54", "#f5f5f5"],
    emblem: { kind: "crescent", color: "#d64545" },
  },
  germany: { kind: "bands", dir: "h", colors: ["#2b2b2b", "#c94747", "#e8c84a"] },
  saudi_arabia: { kind: "field", color: "#3f7d54", emblem: { kind: "bars", color: "#f5f5f5" } },
  argentina: {
    kind: "bands",
    dir: "h",
    colors: ["#7fb2d9", "#f5f5f5", "#7fb2d9"],
    emblem: { kind: "disc", color: "#d8b13c", r: 0.18 },
  },
  australia: { kind: "field", color: "#2e4a8c", emblem: { kind: "star", color: "#f5f5f5" } },
  brazil: { kind: "field", color: "#3f8d4e", emblem: { kind: "diamond", color: "#e8c84a" } },
  canada: {
    kind: "bands",
    dir: "v",
    colors: ["#d64545", "#f5f5f5", "#d64545"],
    emblem: { kind: "maple", color: "#d64545" },
  },
  china: { kind: "field", color: "#c94747", emblem: { kind: "star", color: "#e8c84a" } },
  north_korea: {
    kind: "bands",
    dir: "h",
    colors: ["#2e4a8c", "#f5f5f5", "#c94747", "#f5f5f5", "#2e4a8c"],
    emblem: { kind: "disc-star", disc: "#f5f5f5", star: "#c94747" },
  },
  south_korea: { kind: "field", color: "#f5f5f5", emblem: { kind: "taeguk" } },
  egypt: {
    kind: "bands",
    dir: "h",
    colors: ["#d64545", "#f5f5f5", "#2b2b2b"],
    emblem: { kind: "square", color: "#d8b13c" },
  },
  united_arab_emirates: {
    kind: "bands",
    dir: "h",
    colors: ["#3f7d54", "#f5f5f5", "#2b2b2b"],
    emblem: { kind: "hoist-bar", color: "#c94747" },
  },
  spain: { kind: "bands", dir: "h", colors: ["#c94747", "#e8c84a", "#c94747"] },
  usa: {
    kind: "canton-stripes",
    stripes: ["#c94747", "#f5f5f5"],
    canton: "#2e4a8c",
    starColor: "#f5f5f5",
  },
  france: { kind: "bands", dir: "v", colors: ["#2e5aac", "#f5f5f5", "#d64545"] },
  india: {
    kind: "bands",
    dir: "h",
    colors: ["#e8944a", "#f5f5f5", "#3f7d54"],
    emblem: { kind: "disc", color: "#2e4a8c", r: 0.16 },
  },
  iran: { kind: "bands", dir: "h", colors: ["#3f9e63", "#f5f5f5", "#d64545"] },
  israel: {
    kind: "bands",
    dir: "h",
    colors: ["#f5f5f5", "#2e5aac", "#f5f5f5", "#2e5aac", "#f5f5f5"],
    emblem: { kind: "star", color: "#2e5aac" },
  },
  italy: { kind: "bands", dir: "v", colors: ["#3f7d54", "#f5f5f5", "#d64545"] },
  japan: { kind: "field", color: "#f5f5f5", emblem: { kind: "disc", color: "#d64545" } },
  mali: { kind: "bands", dir: "v", colors: ["#3f9e63", "#e8c84a", "#d64545"] },
  morocco: { kind: "field", color: "#c94747", emblem: { kind: "star", color: "#3f7d54" } },
  mexico: {
    kind: "bands",
    dir: "v",
    colors: ["#3f7d54", "#f5f5f5", "#d64545"],
    emblem: { kind: "disc", color: "#8a6d3b", r: 0.16 },
  },
  pakistan: {
    kind: "bands",
    dir: "v",
    colors: ["#f5f5f5", "#2f6b46", "#2f6b46", "#2f6b46"],
    emblem: { kind: "crescent", color: "#f5f5f5" },
  },
  democratic_republic_congo: {
    kind: "field",
    color: "#4ea8de",
    emblem: { kind: "star", color: "#e8c84a" },
  },
  uk: { kind: "union-jack" },
  russia: { kind: "bands", dir: "h", colors: ["#f5f5f5", "#2e5aac", "#c94747"] },
  senegal: {
    kind: "bands",
    dir: "v",
    colors: ["#3f9e63", "#e8c84a", "#d64545"],
    emblem: { kind: "star", color: "#3f7d54" },
  },
  singapore: {
    kind: "bands",
    dir: "h",
    colors: ["#d64545", "#f5f5f5"],
    emblem: { kind: "crescent", color: "#f5f5f5" },
  },
  tunisia: {
    kind: "field",
    color: "#c94747",
    emblem: { kind: "disc-crescent", disc: "#f5f5f5", mark: "#c94747" },
  },
  turkey: { kind: "field", color: "#c94747", emblem: { kind: "crescent", color: "#f5f5f5" } },
  ukraine: { kind: "bands", dir: "h", colors: ["#2e5aac", "#e8c84a"] },
};

/** Spec d'un pays — repli aplat à la teinte du pays (pays inventés compris). */
export function flagSpec(slug: string, hue = "#64748b"): FlagSpec {
  return FLAG_SPECS[slug] ?? { kind: "field", color: hue };
}

// --- peintre (runtime canvas ; rien à tester ici, les specs le sont) ----------

function star(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number, color: string) {
  ctx.fillStyle = color;
  ctx.beginPath();
  for (let i = 0; i < 5; i += 1) {
    const a = -Math.PI / 2 + (i * 4 * Math.PI) / 5;
    ctx[i ? "lineTo" : "moveTo"](cx + r * Math.cos(a), cy + r * Math.sin(a));
  }
  ctx.closePath();
  ctx.fill();
}

function crescent(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number, color: string) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalCompositeOperation = "destination-out";
  ctx.beginPath();
  ctx.arc(cx + r * 0.45, cy - r * 0.12, r * 0.82, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalCompositeOperation = "source-over";
}

function paintEmblem(ctx: CanvasRenderingContext2D, emblem: Emblem, w: number, h: number) {
  const cx = w / 2;
  const cy = h / 2;
  switch (emblem.kind) {
    case "disc":
      ctx.fillStyle = emblem.color;
      ctx.beginPath();
      ctx.arc(cx, cy, h * (emblem.r ?? 0.3), 0, Math.PI * 2);
      ctx.fill();
      return;
    case "star":
      star(ctx, cx, cy, h * (emblem.r ?? 0.28), emblem.color);
      return;
    case "crescent":
      crescent(ctx, cx, cy, h * 0.3, emblem.color);
      return;
    case "disc-crescent":
      ctx.fillStyle = emblem.disc;
      ctx.beginPath();
      ctx.arc(cx, cy, h * 0.34, 0, Math.PI * 2);
      ctx.fill();
      crescent(ctx, cx, cy, h * 0.24, emblem.mark);
      return;
    case "disc-star":
      ctx.fillStyle = emblem.disc;
      ctx.beginPath();
      ctx.arc(w * 0.32, cy, h * 0.3, 0, Math.PI * 2);
      ctx.fill();
      star(ctx, w * 0.32, cy, h * 0.2, emblem.star);
      return;
    case "diamond":
      ctx.fillStyle = emblem.color;
      ctx.beginPath();
      ctx.moveTo(cx, cy - h * 0.34);
      ctx.lineTo(cx + w * 0.3, cy);
      ctx.lineTo(cx, cy + h * 0.34);
      ctx.lineTo(cx - w * 0.3, cy);
      ctx.closePath();
      ctx.fill();
      return;
    case "maple":
      ctx.fillStyle = emblem.color;
      ctx.beginPath();
      ctx.moveTo(cx, cy - h * 0.3);
      ctx.lineTo(cx + w * 0.1, cy - h * 0.05);
      ctx.lineTo(cx + w * 0.22, cy - h * 0.1);
      ctx.lineTo(cx + w * 0.08, cy + h * 0.18);
      ctx.lineTo(cx, cy + h * 0.3);
      ctx.lineTo(cx - w * 0.08, cy + h * 0.18);
      ctx.lineTo(cx - w * 0.22, cy - h * 0.1);
      ctx.lineTo(cx - w * 0.1, cy - h * 0.05);
      ctx.closePath();
      ctx.fill();
      return;
    case "square":
      ctx.fillStyle = emblem.color;
      ctx.fillRect(cx - w * 0.07, cy - h * 0.14, w * 0.14, h * 0.28);
      return;
    case "bars":
      ctx.fillStyle = emblem.color;
      ctx.fillRect(w * 0.18, h * 0.3, w * 0.64, h * 0.16);
      ctx.fillRect(w * 0.18, h * 0.58, w * 0.5, h * 0.08);
      return;
    case "taeguk":
      ctx.fillStyle = "#c94747";
      ctx.beginPath();
      ctx.arc(cx, cy, h * 0.28, Math.PI, 0);
      ctx.fill();
      ctx.fillStyle = "#2e5aac";
      ctx.beginPath();
      ctx.arc(cx, cy, h * 0.28, 0, Math.PI);
      ctx.fill();
      return;
    case "hoist-triangle":
      ctx.fillStyle = emblem.color;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(w * 0.38, h / 2);
      ctx.lineTo(0, h);
      ctx.closePath();
      ctx.fill();
      return;
    case "hoist-bar":
      ctx.fillStyle = emblem.color;
      ctx.fillRect(0, 0, w * 0.28, h);
      return;
  }
}

/** Peint le drapeau (simplifié) d'un pays dans un rectangle w×h du contexte. */
export function paintFlag(
  ctx: CanvasRenderingContext2D,
  slug: string,
  w: number,
  h: number,
  hue?: string,
): void {
  const spec = flagSpec(slug, hue);
  switch (spec.kind) {
    case "bands": {
      const n = spec.colors.length;
      spec.colors.forEach((color, i) => {
        ctx.fillStyle = color;
        if (spec.dir === "h") ctx.fillRect(0, (i * h) / n, w, h / n + 0.5);
        else ctx.fillRect((i * w) / n, 0, w / n + 0.5, h);
      });
      if (spec.emblem) paintEmblem(ctx, spec.emblem, w, h);
      break;
    }
    case "field":
      ctx.fillStyle = spec.color;
      ctx.fillRect(0, 0, w, h);
      if (spec.emblem) paintEmblem(ctx, spec.emblem, w, h);
      break;
    case "canton-stripes": {
      for (let i = 0; i < 7; i += 1) {
        ctx.fillStyle = spec.stripes[i % 2];
        ctx.fillRect(0, (i * h) / 7, w, h / 7 + 0.5);
      }
      ctx.fillStyle = spec.canton;
      ctx.fillRect(0, 0, w * 0.42, h * 0.45);
      ctx.fillStyle = spec.starColor;
      for (let y = 0.08; y < 0.42; y += 0.12) {
        for (let x = 0.05; x < 0.4; x += 0.09) {
          ctx.fillRect(w * x, h * y, Math.max(1, w * 0.03), Math.max(1, w * 0.03));
        }
      }
      break;
    }
    case "union-jack": {
      ctx.fillStyle = "#2e4a8c";
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = "#f5f5f5";
      ctx.lineWidth = h * 0.19;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(w, h);
      ctx.moveTo(w, 0);
      ctx.lineTo(0, h);
      ctx.stroke();
      ctx.lineWidth = h * 0.28;
      ctx.beginPath();
      ctx.moveTo(w / 2, 0);
      ctx.lineTo(w / 2, h);
      ctx.moveTo(0, h / 2);
      ctx.lineTo(w, h / 2);
      ctx.stroke();
      ctx.strokeStyle = "#c94747";
      ctx.lineWidth = h * 0.14;
      ctx.beginPath();
      ctx.moveTo(w / 2, 0);
      ctx.lineTo(w / 2, h);
      ctx.moveTo(0, h / 2);
      ctx.lineTo(w, h / 2);
      ctx.stroke();
      break;
    }
  }
  ctx.strokeStyle = "rgba(0,0,0,.35)";
  ctx.lineWidth = 1;
  ctx.strokeRect(0.5, 0.5, w - 1, h - 1);
}
