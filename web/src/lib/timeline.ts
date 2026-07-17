/** Frise chronologique (G15) — mapping pur rounds → crans, sans React.
 *
 * La frise raconte la partie : un cran par round (titre de l'événement GM, teinté par
 * le delta U du round) + badges des moments spéciaux. Les données viennent toutes de
 * `getGame` (`detail.rounds[]`) — aucun endpoint nouveau. L'`index` est 0-based :
 * même sémantique que le `onSelect` du scrubber StageBand (clic cran k → onSelect(k-1)).
 */

export type TimelineBadge = "motion" | "suspension" | "flash" | "treaty";

export type TimelineTone = "utopia" | "dystopia" | "flat";

/** Vue structurelle minimale d'un round (sous-ensemble de RoundView — fixtures de
 * test légères, et le composant accepte les vrais rounds tels quels). */
export type TimelineRound = {
  round_no: number;
  event?: { title?: string; event_type?: string } | null;
  judge?: {
    suspension?: { country?: string; upheld?: boolean; reasoning?: string } | null;
    treaties?: { ratified?: unknown[] } | null;
  } | null;
  trajectory?: { utopia?: number } | null;
  transcript?: { speaker: string; content: string }[];
};

export type TimelineNotch = {
  index: number; // 0-based — sémantique onSelect du StageBand
  roundNo: number; // 1-based — affichage
  title: string; // titre de l'événement GM ("" si round sans événement)
  auto: boolean; // aucun événement porté par le round (cran « auto »)
  human: boolean; // événement décrété par l'humain (event_type "human")
  u: number; // indice U en fin de round (0,5 si inconnu)
  deltaU: number; // variation vs round précédent (départ 0,5)
  tone: TimelineTone; // teinte de la pastille (or/vert ↔ rouge)
  badges: TimelineBadge[];
};

const U_START = 0.5;
const FLAT_EPSILON = 0.002; // en-dessous, le round n'a pas « bougé le monde »

/** Le préfixe posé par le moteur quand le GM injecte un fait nouveau en séance
 * (simulation/live_round.py — entrée de transcript du speaker "gm"). */
const FLASH_PREFIX = "FAIT NOUVEAU";

function badgesOf(round: TimelineRound): TimelineBadge[] {
  const badges: TimelineBadge[] = [];
  const suspension = round.judge?.suspension;
  if (suspension) {
    badges.push("motion"); // une motion a été débattue et arbitrée ce round
    if (suspension.upheld) badges.push("suspension");
  }
  if (
    round.transcript?.some(
      (e) => e.speaker === "gm" && e.content.startsWith(FLASH_PREFIX),
    )
  ) {
    badges.push("flash");
  }
  if ((round.judge?.treaties?.ratified?.length ?? 0) > 0) badges.push("treaty");
  return badges;
}

/** rounds → crans : n rounds font n crans, dans l'ordre. */
export function buildTimeline(rounds: TimelineRound[]): TimelineNotch[] {
  let previousU = U_START;
  return rounds.map((round, index) => {
    const u = round.trajectory?.utopia ?? previousU;
    const deltaU = u - previousU;
    previousU = u;
    return {
      index,
      roundNo: round.round_no,
      title: round.event?.title ?? "",
      auto: !round.event?.title,
      human: round.event?.event_type === "human",
      u,
      deltaU,
      tone:
        Math.abs(deltaU) < FLAT_EPSILON ? "flat" : deltaU > 0 ? "utopia" : "dystopia",
      badges: badgesOf(round),
    };
  });
}

/** Un pas de navigation (flèches ← / →), borné à [0, total-1]. */
export function stepNotch(current: number, delta: -1 | 1, total: number): number {
  if (total <= 0) return 0;
  return Math.min(Math.max(current + delta, 0), total - 1);
}
