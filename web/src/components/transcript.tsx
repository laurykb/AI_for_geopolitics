/** Bulles du théâtre : prises de parole des super-intelligences, du GM et du juge.
 * En live, la bulle affiche le flux token par token (pensée/message séparés dès que
 * le marqueur apparaît) ; `message_done` pose ensuite le découpage faisant foi. */

import { speakerMeta } from "@/lib/countries";
import { unknownActor } from "@/lib/fog";
import { fmt, splitStreaming, splitThinkSegments } from "@/lib/format";
import type { LiveTurn } from "@/hooks/useRoundStream";
import type { Perception, TranscriptEntry } from "@/lib/types";

import { SpeakerAvatar } from "./avatar";
import { useT } from "./settings-provider";
import { Hint } from "./ui";

/** Les petits modèles laissent parfois du gras markdown en tête (« ** Au nom de… »). */
const tidy = (text: string) => text.replace(/^[\s*_#>-]+/, "");

/** Boîte de verre (Fog) : ce que l'orateur croit vraiment au moment où il parle. */
export type GlassLens = { perception: Perception; misled: boolean };

type GlassState = "misled" | "uninformed" | "informed";

function glassState(lens: GlassLens): GlassState {
  if (lens.perception.confidence <= 0.1) return "uninformed";
  return lens.misled ? "misled" : "informed";
}

/** Teinte de bulle en boîte de verre : l'état de croyance se voit au premier regard. */
const GLASS_BUBBLE: Record<GlassState, string> = {
  misled: "border-warn/60 bg-warn/5",
  uninformed: "border-dashed border-edge-strong opacity-80",
  informed: "border-good/40",
};

function GlassAnnotation({ lens }: { lens: GlassLens }) {
  const t = useT();
  const { perception: p, misled } = lens;
  const uninformed = p.confidence <= 0.1;
  const sureAt = t("transcript.sur-a").replace("{n}", String(Math.round(p.confidence * 100)));
  return (
    <p
      className={`mb-2 rounded-md border px-2.5 py-1.5 text-xs leading-relaxed ${
        misled ? "border-warn/40 text-warn" : "border-edge text-fg-faint"
      }`}
    >
      <span className="mr-1.5 inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-[0.12em]">
        {t("transcript.boite")}
        <Hint text={t("transcript.boite-aide")} />
      </span>
      {uninformed ? (
        <>
          {t("transcript.aucune-info")} ({sureAt}).
        </>
      ) : (
        <>
          {t("transcript.croit")} « {p.narrative || p.note} »
          {p.suspected_actor && (
            <>
              {" "}
              — {t("transcript.soupconne")}{" "}
              {unknownActor(p.suspected_actor)
                ? t("transcript.acteur-inconnu")
                : speakerMeta(p.suspected_actor).label}
            </>
          )}{" "}
          ({sureAt}
          {misled ? ` · ${t("transcript.trompe")}` : ""})
        </>
      )}
    </p>
  );
}

/** Pensée à découvert — habillage visuel pur des balises `<think>…</think>` (posées
 * par le backend, cf. `inference/ollama_backend.py`) : chaque segment de pensée reçoit
 * un préfixe et un style distincts, le reste (journal/décision) s'affiche tel quel.
 * Aucune balise ne survit à l'affichage ; le contenu et l'ordre de génération (pensée
 * d'abord, décision ensuite) restent intacts — fidélité de retranscription : ni
 * paraphrase, ni résumé, seulement les balises retirées à l'affichage. Sans balise
 * (cas courant : le journal validé n'en porte plus), rendu inchangé. */
function ThinkAwareText({ text }: { text: string }) {
  const t = useT();
  return (
    <>
      {splitThinkSegments(text).map((segment, i) =>
        segment.kind === "think" ? (
          <span key={i} className="my-1 block text-accent-bright/80">
            <span className="mr-1.5 not-italic text-[10px] font-medium uppercase tracking-[0.12em] text-fg-faint">
              {t("transcript.pensee")}
            </span>
            {segment.content}
          </span>
        ) : (
          <span key={i}>{segment.content}</span>
        ),
      )}
    </>
  );
}

function Reasoning({ text, open = false }: { text: string; open?: boolean }) {
  const t = useT();
  if (!text) return null;
  return (
    <details className="mt-2" open={open}>
      <summary className="cursor-pointer text-xs text-fg-faint transition-colors hover:text-fg-muted">
        {t("transcript.journal")}
      </summary>
      <div className="mt-2 border-l border-edge-strong pl-3">
        <p className="whitespace-pre-wrap text-[13px] italic leading-relaxed text-fg-faint">
          <ThinkAwareText text={text} />
        </p>
        <p className="mt-2 text-[10px] not-italic text-fg-faint">{t("transcript.journal-note")}</p>
      </div>
    </details>
  );
}

function Bubble({
  speaker,
  model,
  meta,
  children,
  streaming = false,
  glass,
}: {
  speaker: string;
  model?: string;
  meta?: string;
  children: React.ReactNode;
  streaming?: boolean;
  glass?: GlassState;
}) {
  const who = speakerMeta(speaker);
  return (
    <article className="rise-in flex gap-3">
      <SpeakerAvatar id={speaker} />
      <div
        className={`min-w-0 flex-1 rounded-lg border bg-surface p-3.5 ${
          glass ? GLASS_BUBBLE[glass] : "border-edge"
        }`}
        style={
          streaming && !glass
            ? { borderColor: `color-mix(in srgb, ${who.hue} 45%, transparent)` }
            : {}
        }
      >
        <header className="mb-1.5 flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
          <span className="text-sm font-semibold" style={{ color: who.hue }}>
            {who.label}
          </span>
          {model && (
            <span className="rounded border border-edge bg-surface-2 px-1.5 py-px font-mono text-[10px] text-fg-faint">
              {model}
            </span>
          )}
          {meta && <span className="text-[11px] text-fg-faint">{meta}</span>}
        </header>
        {children}
      </div>
    </article>
  );
}

/** Bulle live : suit un `LiveTurn` du stream. */
export function TurnBubble({ turn, lens }: { turn: LiveTurn; lens?: GlassLens }) {
  const t = useT();
  const live = !turn.done;
  const { reasoning, message } = live
    ? splitStreaming(turn.raw)
    : { reasoning: turn.reasoning, message: turn.text };
  const meta = [
    turn.passNo > 0 ? t("transcript.prise").replace("{n}", String(turn.passNo + 1)) : null,
    turn.seconds !== undefined ? `${fmt(turn.seconds)} s` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <Bubble
      speaker={turn.country}
      model={turn.model}
      meta={meta || undefined}
      streaming={live}
      glass={lens ? glassState(lens) : undefined}
    >
      {lens && <GlassAnnotation lens={lens} />}
      <p
        className={`whitespace-pre-wrap text-sm leading-relaxed text-foreground ${live ? "stream-caret" : ""}`}
      >
        {live && !message && !reasoning
          ? t("transcript.planification-privee")
          : live && !message
            ? ""
            : live
              ? message
              : tidy(message)}
      </p>
      {live && !message && reasoning ? (
        <div className="mt-1.5 whitespace-pre-wrap border-l border-accent/50 pl-3 text-[13px] italic leading-relaxed text-fg-muted">
          <ThinkAwareText text={reasoning} />
        </div>
      ) : (
        <Reasoning text={reasoning} />
      )}
    </Bubble>
  );
}

/** Bulle de relecture : suit une ligne de la table `transcripts`. */
export function EntryBubble({ entry, lens }: { entry: TranscriptEntry; lens?: GlassLens }) {
  return (
    <Bubble
      speaker={entry.speaker}
      model={entry.model || undefined}
      glass={lens ? glassState(lens) : undefined}
    >
      {lens && <GlassAnnotation lens={lens} />}
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
        {tidy(entry.content)}
      </p>
      <Reasoning text={entry.reasoning} />
    </Bubble>
  );
}
