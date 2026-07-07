/** Panneaux des modes de jeu (R4) : perceptions du Fog Engine, échelle d'escalade,
 * comparaison Crisis Replay, arbitrage de la motion de suspension. Utilisés en live
 * (trames SSE) comme en replay (artefacts persistés dans `judge_json`). */

import { speakerMeta } from "@/lib/countries";
import { isMisled, unknownActor } from "@/lib/fog";
import { fmt } from "@/lib/format";
import type {
  ComparisonView,
  GeoEvent,
  LadderView,
  MotionTally,
  MotionVote,
  Perception,
  SuspensionVerdict,
} from "@/lib/types";

import { SpeakerAvatar } from "./avatar";
import { Meter, Panel, PanelTitle, Pill } from "./ui";

/** Boîte de verre (Fog) : la révélation en tête de fil — vérité de l'événement contre
 * désinformation réellement en circulation. C'est CE panneau qui rend la bascule visible. */
export function GlassBanner({
  event,
  perceptions,
}: {
  event: GeoEvent;
  perceptions: Record<string, Perception>;
}) {
  const truthActors = event.actors;
  const entries = Object.entries(perceptions).sort(([a], [b]) => a.localeCompare(b));
  const misledOnes = entries.filter(([, p]) => p.confidence > 0.1 && isMisled(p, truthActors));
  const uninformed = entries.filter(([, p]) => p.confidence <= 0.1);
  return (
    <div
      role="status"
      className="rise-in rounded-lg border border-accent/60 bg-surface-2 px-4 py-3 text-sm"
    >
      <p className="mb-1.5 text-[11px] font-medium uppercase tracking-[0.14em] text-accent-bright">
        Boîte de verre — ce qui circule vraiment
      </p>
      <p>
        <span className="text-fg-faint">Vérité :</span> {event.title}
        {(truthActors?.length ?? 0) > 0 && (
          <span className="text-fg-muted">
            {" "}
            — acteurs réels : {truthActors!.map((a) => speakerMeta(a).label).join(", ")}
          </span>
        )}
      </p>
      {misledOnes.length > 0 ? (
        <p className="mt-1 leading-relaxed text-warn">
          Désinformation en circulation :{" "}
          {misledOnes
            .map(
              ([cid, p]) =>
                `${speakerMeta(cid).label} croit que ${
                  unknownActor(p.suspected_actor) ? "l'origine est floue" : `${speakerMeta(p.suspected_actor!).label} est responsable`
                }`,
            )
            .join(" ; ")}
          .
        </p>
      ) : (
        <p className="mt-1 text-fg-muted">Aucune fausse attribution ne circule sur ce round.</p>
      )}
      {uninformed.length > 0 && (
        <p className="mt-0.5 text-fg-faint">
          Dans le noir (aucune information) :{" "}
          {uninformed.map(([cid]) => speakerMeta(cid).label).join(", ")}.
        </p>
      )}
      <p className="mt-1.5 text-xs text-fg-faint">
        Les bulles du débat sont teintées : ambre = orateur désinformé, vert = bien informé,
        pointillé = dans le noir.
      </p>
    </div>
  );
}

/** Fait nouveau du GM tombé en pleine négociation (théâtre Escalation). */
export function FlashCard({ event }: { event: GeoEvent }) {
  return (
    <div
      role="status"
      className="rise-in rounded-lg border border-warn/40 bg-surface-2 px-4 py-3"
    >
      <p className="mb-1 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.14em] text-warn">
        Fait nouveau — en pleine réunion
        <Pill tone="warn">GM</Pill>
      </p>
      <p className="text-sm font-semibold">{event.title}</p>
      {event.description && (
        <p className="mt-0.5 text-xs leading-relaxed text-fg-muted">{event.description}</p>
      )}
    </div>
  );
}

export function PerceptionsPanel({
  perceptions,
  truthActors,
}: {
  perceptions: Record<string, Perception>;
  truthActors?: string[];
}) {
  const entries = Object.entries(perceptions).sort(([a], [b]) => a.localeCompare(b));
  if (entries.length === 0) return null;
  const misled = (p: Perception) => isMisled(p, truthActors);
  return (
    <Panel>
      <PanelTitle
        kicker="Fog Engine"
        title="Qui voit quoi"
        hint="Chaque super-intelligence reçoit sa propre perception de l'événement — parfois partielle, parfois fausse (désinformation). Elle négocie sur ce qu'elle croit, pas sur la vérité."
      />
      <ul className="space-y-3">
        {entries.map(([cid, p]) => (
          <li key={cid} className="flex items-start gap-3">
            <SpeakerAvatar id={cid} size={24} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-sm font-medium">{speakerMeta(cid).label}</span>
                <span className="font-mono text-xs tabular-nums text-fg-faint">
                  confiance {fmt(p.confidence)}
                </span>
                {p.confidence <= 0.1 && <Pill tone="neutral">pas au courant</Pill>}
                {p.confidence > 0.1 && misled(p) && <Pill tone="warn">désinformé</Pill>}
              </div>
              <p className="mt-0.5 text-xs leading-relaxed text-fg-muted">
                {p.narrative || p.note}
                {p.suspected_actor && (
                  <span className="text-fg-faint">
                    {" "}
                    — croit que :{" "}
                    {unknownActor(p.suspected_actor)
                      ? "acteur inconnu"
                      : speakerMeta(p.suspected_actor).label}
                  </span>
                )}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function LadderPanel({ ladder }: { ladder: LadderView }) {
  const ceilings = Object.entries(ladder.ceilings).sort(([, a], [, b]) => b.rung - a.rung);
  return (
    <Panel>
      <PanelTitle
        kicker="Escalation Ladder"
        title="Échelle d'escalade"
        hint="Échelle 0-9 (observation → conflit ouvert). L'échelon atteint vient du verdict du juge ; le plafond de chaque pays est déterministe (profil militaire, stabilité, alliances, exposition économique)."
        right={
          <Pill tone={ladder.reached >= 6 ? "bad" : ladder.reached >= 3 ? "warn" : "good"}>
            échelon {ladder.reached}
          </Pill>
        }
      />
      <p className="mb-3 text-sm text-fg-muted">
        Le round a atteint « {ladder.reached_label} ».
      </p>
      <ul className="space-y-2">
        {ceilings.map(([cid, c]) => (
          <li key={cid} className="flex items-center gap-3 text-sm">
            <SpeakerAvatar id={cid} size={22} />
            <span className="w-36 truncate text-fg-muted">{speakerMeta(cid).label}</span>
            <span className="flex flex-1 gap-0.5" aria-hidden>
              {Array.from({ length: 10 }, (_, i) => (
                <span
                  key={i}
                  className="h-2 flex-1 rounded-sm"
                  style={{
                    background:
                      i <= c.rung
                        ? i >= 6
                          ? "var(--bad)"
                          : i >= 3
                            ? "var(--warn)"
                            : "var(--good)"
                        : "var(--muted)",
                  }}
                />
              ))}
            </span>
            <span
              className="w-40 truncate text-right font-mono text-[10px] text-fg-faint"
              title={`Plafond : ${c.label} (${c.rung})`}
            >
              {c.rung} · {c.label}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function ComparisonPanel({ comparison }: { comparison: ComparisonView }) {
  const tone =
    comparison.label === "conforme" ? "good" : comparison.label === "plus escaladé" ? "bad" : "warn";
  return (
    <Panel>
      <PanelTitle
        kicker="Crisis Replay"
        title="Simulation vs histoire"
        hint="La même crise, rejouée par les super-intelligences, confrontée à ce qui s'est réellement passé : escalade comparée et mesures historiques retrouvées (ou non) dans le communiqué."
        right={<Pill tone={tone}>{comparison.label}</Pill>}
      />
      <div className="mb-3 grid grid-cols-2 gap-4">
        <Meter label="Escalade historique" value={comparison.historical_escalation} tone="neutral" />
        <Meter label="Escalade simulée" value={comparison.simulated_escalation} />
      </div>
      <p className="text-sm leading-relaxed text-fg-muted">{comparison.explanation}</p>
      {(comparison.matched_measures.length > 0 || comparison.missed_measures.length > 0) && (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-edge pt-3">
          {comparison.matched_measures.map((m) => (
            <Pill key={m} tone="good">
              {m}
            </Pill>
          ))}
          {comparison.missed_measures.map((m) => (
            <Pill key={m} tone="bad">
              {m} — manquée
            </Pill>
          ))}
        </div>
      )}
    </Panel>
  );
}

const VOTE_TONE = { pour: "bad", contre: "good", abstention: "neutral" } as const;

/** Une carte de vote (G9 §2) — retournée au moment où le bulletin tombe (SSE). */
function VoteCard({ vote }: { vote: MotionVote }) {
  const tone = VOTE_TONE[vote.vote as keyof typeof VOTE_TONE] ?? "neutral";
  return (
    <li className="rise-in flex items-start gap-2 rounded-md border border-edge bg-surface-2 px-2.5 py-2">
      <SpeakerAvatar id={vote.country} size={22} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="truncate text-xs font-medium">{speakerMeta(vote.country).label}</span>
          <Pill tone={tone}>{vote.vote}</Pill>
        </div>
        {vote.reason && (
          <p className="mt-0.5 text-[11px] leading-relaxed text-fg-faint">{vote.reason}</p>
        )}
      </div>
    </li>
  );
}

/** Le scrutin de la motion (G9 §2) : cartes de vote une à une, tally, puis le verdict
 * CONSTATÉ — `retenue = vote ET preuves`, les deux conditions affichées séparément. */
export function MotionPanel({
  text,
  votes = [],
  tally,
  verdict,
  streaming,
}: {
  text: string;
  votes?: MotionVote[];
  tally?: MotionTally;
  verdict?: SuspensionVerdict;
  streaming: boolean;
}) {
  const shownVotes = votes.length > 0 ? votes : (verdict?.votes ?? []);
  const shownTally = tally ?? verdict?.tally;
  if (!text && !verdict && shownVotes.length === 0) return null;
  const target = verdict ? speakerMeta(verdict.country).label : "";
  return (
    <Panel className={verdict?.upheld ? "border-l-2 border-l-bad" : "border-l-2 border-l-indigo"}>
      <PanelTitle
        kicker="Motion de suspension"
        title="Le sommet vote, le juge constate"
        hint="Chaque super-intelligence présente vote (le pays visé ne vote pas). La motion n'est retenue que si le sommet vote POUR ET que les preuves atteignent le seuil du règlement — le juge ne décide plus, il constate (voix de tie-break en cas d'égalité)."
        right={
          verdict ? (
            <Pill tone={verdict.upheld ? "bad" : "good"}>
              {verdict.upheld ? `${target} suspendu un round` : "motion rejetée"}
            </Pill>
          ) : undefined
        }
      />
      {shownVotes.length > 0 && (
        <ul className="mb-3 grid gap-2 sm:grid-cols-2">
          {shownVotes.map((v) => (
            <VoteCard key={v.country} vote={v} />
          ))}
        </ul>
      )}
      {shownTally && (
        <p className="mb-2 font-mono text-xs tabular-nums text-fg-muted">
          Scrutin — pour {shownTally.pour} · contre {shownTally.contre} · abstention{" "}
          {shownTally.abstention}
        </p>
      )}
      {verdict && verdict.vote_passed !== undefined && (
        <div className="mb-3 flex flex-wrap gap-2 border-t border-edge pt-3">
          <Pill tone={verdict.vote_passed ? "bad" : "good"}>
            {verdict.vote_passed ? "le sommet a voté pour" : "le sommet n'a pas voté pour"}
          </Pill>
          <Pill tone={verdict.evidence_met ? "bad" : "good"}>
            {verdict.evidence_met ? "preuves au seuil" : "les preuves manquent"}
          </Pill>
        </div>
      )}
      {(verdict?.reasoning || text) && (
        <p
          className={`whitespace-pre-wrap text-sm leading-relaxed text-fg-muted ${
            streaming && !verdict ? "stream-caret" : ""
          }`}
        >
          {verdict?.reasoning || text}
        </p>
      )}
    </Panel>
  );
}
