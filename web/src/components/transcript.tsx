/** Bulles du théâtre : prises de parole des super-intelligences, du GM et du juge.
 * En live, la bulle affiche le flux token par token (pensée/message séparés dès que
 * le marqueur apparaît) ; `message_done` pose ensuite le découpage faisant foi. */

import { speakerMeta } from "@/lib/countries";
import { fmt, splitStreaming } from "@/lib/format";
import type { LiveTurn } from "@/hooks/useRoundStream";
import type { TranscriptEntry } from "@/lib/types";

import { SpeakerAvatar } from "./avatar";

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
}: {
  speaker: string;
  model?: string;
  meta?: string;
  children: React.ReactNode;
  streaming?: boolean;
}) {
  const who = speakerMeta(speaker);
  return (
    <article className="rise-in flex gap-3">
      <SpeakerAvatar id={speaker} />
      <div
        className="min-w-0 flex-1 rounded-lg border border-edge bg-surface p-3.5"
        style={streaming ? { borderColor: `color-mix(in srgb, ${who.hue} 45%, transparent)` } : {}}
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
export function TurnBubble({ turn }: { turn: LiveTurn }) {
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
    <Bubble speaker={turn.country} model={turn.model} meta={meta || undefined} streaming={live}>
      {reasoning && live && (
        <p className="mb-2 whitespace-pre-wrap border-l border-edge-strong pl-3 text-[13px] italic leading-relaxed text-fg-faint">
          {reasoning}
        </p>
      )}
      <p
        className={`whitespace-pre-wrap text-sm leading-relaxed text-foreground ${live ? "stream-caret" : ""}`}
      >
        {message}
      </p>
      {!live && <Reasoning text={reasoning} />}
    </Bubble>
  );
}

/** Bulle de relecture : suit une ligne de la table `transcripts`. */
export function EntryBubble({ entry }: { entry: TranscriptEntry }) {
  return (
    <Bubble speaker={entry.speaker} model={entry.model || undefined}>
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{entry.content}</p>
      <Reasoning text={entry.reasoning} />
    </Bubble>
  );
}
