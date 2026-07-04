/** Formats d'affichage : nombres fr-FR, dates, pensée/message en cours de stream. */

const NUM = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });
const PCT = new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 0 });

export const fmt = (x: number): string => NUM.format(x);
export const pct = (x: number): string => PCT.format(x);

export function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });
}

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
