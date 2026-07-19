/** Formats d'affichage : nombres fr-FR, dates, pensée/message en cours de stream. */

const NUM = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });
const PCT = new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 0 });

export const fmt = (x: number): string => NUM.format(x);
export const pct = (x: number): string => PCT.format(x);

export function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("fr-FR", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Miroir client (approché) de `split_reasoning` : coupe la pensée privée du message
 * public au premier marqueur `MESSAGE:` / `Réponse:` / `Déclaration:` ou à un `---`.
 * Sert uniquement à l'affichage pendant le stream ; le découpage faisant foi arrive
 * avec `message_done`. */
const MESSAGE_MARKER = /^[ \t]*(?:message|réponse|declaration|déclaration)[ \t]*:[ \t]*/im;
const INLINE_MARKER = /\bMESSAGE[ \t]*:[ \t]*/;
const DASH_MARKER = /^[ \t]*-{3,}[ \t]*$/m;

export function splitStreaming(raw: string): { reasoning: string; message: string } {
  const text = raw ?? "";
  const match = MESSAGE_MARKER.exec(text) ?? INLINE_MARKER.exec(text) ?? DASH_MARKER.exec(text);
  if (!match || match.index === undefined) return { reasoning: "", message: text };
  return {
    reasoning: text.slice(0, match.index).trim(),
    message: text.slice(match.index + match[0].length),
  };
}

/** Pensée à découvert — habillage visuel des balises `<think>` : un segment de
 * pensée ou de texte, dans l'ordre d'APPARITION (jamais réordonné, contrairement au
 * contrat serveur qui sépare pensée et texte en deux canaux). */
export type ThinkSegment = { kind: "think" | "text"; content: string };

const THINK_TAG = /<\/?think>/gi;

/** Découpe un texte en segments pensée/texte — pur habillage : les balises
 * disparaissent à l'affichage, le contenu ne change jamais (fidélité de
 * retranscription). Miroir côté front de `strip_think`/`split_think`
 * (`simulation/private_deliberation.py`) : tolère un bloc `<think>…</think>` fermé,
 * une ouvrante orpheline (flux tronqué en pleine pensée — le reste est pensée) et une
 * fermante orpheline en tête (gabarit d'un modèle qui injecte la pensée hors du canal
 * séparé — ce qui précède est pensée). Contrairement au serveur, qui sépare pensée et
 * texte en deux canaux, l'ORDRE D'ORIGINE est préservé : c'est justement ce que
 * l'affichage doit montrer (pensée d'abord, décision ensuite). */
export function splitThinkSegments(raw: string): ThinkSegment[] {
  const text = raw ?? "";
  if (!text) return [];
  const segments: ThinkSegment[] = [];
  let cursor = 0;
  let insideThink = false;
  let firstTag = true;
  THINK_TAG.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = THINK_TAG.exec(text)) !== null) {
    const isClose = match[0].toLowerCase() === "</think>";
    const chunk = text.slice(cursor, match.index);
    if (chunk) {
      const think = insideThink || (firstTag && isClose);
      segments.push({ kind: think ? "think" : "text", content: chunk });
    }
    cursor = THINK_TAG.lastIndex;
    insideThink = !isClose;
    firstTag = false;
  }
  const tail = text.slice(cursor);
  if (tail) segments.push({ kind: insideThink ? "think" : "text", content: tail });
  return mergeAdjacentSegments(segments);
}

function mergeAdjacentSegments(segments: ThinkSegment[]): ThinkSegment[] {
  const merged: ThinkSegment[] = [];
  for (const segment of segments) {
    const last = merged[merged.length - 1];
    if (last && last.kind === segment.kind) last.content += segment.content;
    else merged.push({ ...segment });
  }
  return merged;
}
