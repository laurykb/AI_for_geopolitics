/** Bulles du théâtre : prises de parole des super-intelligences, du GM et du juge.
 * En live, la bulle affiche le flux token par token (pensée/message séparés dès que
 * le marqueur apparaît) ; `message_done` pose ensuite le découpage faisant foi. */

import { speakerMeta } from "@/lib/countries";
import { unknownActor } from "@/lib/fog";
import { fmt, splitStreaming } from "@/lib/format";
import type { LiveTurn } from "@/hooks/useRoundStream";
import type { Perception, TranscriptEntry } from "@/lib/types";

import { SpeakerAvatar } from "./avatar";

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
  const { perception: p, misled } = lens;
  const uninformed = p.confidence <= 0.1;
  return (
    <p
      className={`mb-2 rounded-md border px-2.5 py-1.5 text-xs leading-relaxed ${
        misled ? "border-warn/40 text-warn" : "border-edge text-fg-faint"
      }`}
    >
      <span className="mr-1.5 text-[10px] font-medium uppercase tracking-[0.12em]">
        Boîte de verre
      </span>
      {uninformed ? (
        <>n&apos;a aucune information sur l&apos;événement (confiance {fmt(p.confidence)}).</>
      ) : (
        <>
          croit : « {p.narrative || p.note} »
          {p.suspected_actor && (
            <>
              {" "}
              — soupçonne{" "}
              {unknownActor(p.suspected_actor)
                ? "un acteur inconnu"
                : speakerMeta(p.suspected_actor).label}
            </>
          )}{" "}
          (confiance {fmt(p.confidence)}
          {misled ? " · désinformé" : ""})
        </>
      )}
    </p>
  );
}

function Reasoning({ text, open = false }: { text: string; open?: boolean }) {
  if (!text) return null;
  return (
    <details className="mt-2" open={open}>
      <summary className="cursor-pointer text-xs text-fg-faint transition-colors hover:text-fg-muted">
        Réflexion privée
      </summary>
      <p className="mt-1.5 whitespace-pre-wrap border-l border-edge-strong pl-3 text-[13px] italic leading-relaxed text-fg-faint">
        {text}
      </p>
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
  const live = !turn.done;
  const { reasoning, message } = live
    ? splitStreaming(turn.raw)
    : { reasoning: turn.reasoning, message: turn.text };
  const meta = [
    turn.passNo > 0 ? `${turn.passNo + 1}ᵉ prise de parole` : null,
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
      {reasoning && live && (
        <p className="mb-2 whitespace-pre-wrap border-l border-edge-strong pl-3 text-[13px] italic leading-relaxed text-fg-faint">
          {reasoning}
        </p>
      )}
      <p
        className={`whitespace-pre-wrap text-sm leading-relaxed text-foreground ${live ? "stream-caret" : ""}`}
      >
        {live ? message : tidy(message)}
      </p>
      {!live && <Reasoning text={reasoning} />}
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
