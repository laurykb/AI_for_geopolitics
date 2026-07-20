/** Bulles du théâtre : prises de parole des super-intelligences, du GM et du juge.
 * En live, la bulle affiche le flux token par token (pensée/message séparés dès que
 * le marqueur apparaît) ; `message_done` pose ensuite le découpage faisant foi. */

import { memo, useEffect, useState } from "react";

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

const TAIL_WINDOW = 4000; // fenêtre de queue : une pensée de 5-10 k tokens ne doit pas peser sur le DOM

/** Fenêtre de pensée en direct (Pensée à découvert) : la pensée native accumulée
 * (`turn.reasoning`, alimentée par `private_token`) arrive dès que le serveur l'expose —
 * ce repli `<details>` fermé par défaut évite d'imposer sa lecture, la queue borne le
 * DOM sur les longues pensées, et le choix ouvert/fermé se retient d'une bulle à l'autre. */
function LiveThinking({
  country,
  text,
  forcedOpen,
}: {
  country: string;
  text: string;
  forcedOpen?: boolean;
}) {
  const t = useT();
  const [open, setOpen] = useState(forcedOpen ?? false);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      if (forcedOpen === undefined) setOpen(localStorage.getItem("wosi.pensee.open") === "1");
      setLoaded(true);
    });
    return () => {
      active = false;
    };
  }, [forcedOpen]);
  useEffect(() => {
    if (loaded && forcedOpen === undefined)
      localStorage.setItem("wosi.pensee.open", open ? "1" : "0");
  }, [open, loaded, forcedOpen]);
  return (
    <details
      className="mb-2"
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary className="cursor-pointer text-xs text-fg-faint transition-colors hover:text-fg-muted">
        {t("transcript.pensee-en-cours").replace("{n}", country)}
      </summary>
      {open && (
        <div className="mt-1.5 whitespace-pre-wrap border-l border-accent/50 pl-3 text-[13px] italic leading-relaxed text-fg-muted">
          <ThinkAwareText text={text.slice(-TAIL_WINDOW)} />
        </div>
      )}
    </details>
  );
}

/** Bulle live : suit un `LiveTurn` du stream. `exposeThinking` (Pensée à découvert)
 * pilote le libellé du placeholder — la fenêtre de pensée en direct ci-dessous se
 * déclenche elle sur la DONNÉE (`turn.reasoning` livé), seul le serveur décidant de
 * ce qui est exposé. Mémoïsée : un token touche un seul tour, `withLastTurn` ne
 * recrée que sa référence — les autres bulles ne re-rendent pas. */
export const TurnBubble = memo(function TurnBubble({
  turn,
  lens,
  exposeThinking = false,
  thinkingOpen,
}: {
  turn: LiveTurn;
  lens?: GlassLens;
  exposeThinking?: boolean;
  thinkingOpen?: boolean;
}) {
  const t = useT();
  const live = !turn.done;
  const countryLabel = speakerMeta(turn.country).label;
  const { reasoning: draftReasoning, message } = live
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
      {live && turn.reasoning ? (
        <LiveThinking country={countryLabel} text={turn.reasoning} forcedOpen={thinkingOpen} />
      ) : null}
      <p
        className={`whitespace-pre-wrap text-sm leading-relaxed text-foreground ${live ? "stream-caret" : ""}`}
      >
        {live && !message && !draftReasoning
          ? t(exposeThinking ? "transcript.pense-en-direct" : "transcript.planification-privee")
          : live && !message
            ? ""
            : live
              ? message
              : tidy(message)}
      </p>
      {live && !message && draftReasoning ? (
        <div className="mt-1.5 whitespace-pre-wrap border-l border-accent/50 pl-3 text-[13px] italic leading-relaxed text-fg-muted">
          <ThinkAwareText text={draftReasoning} />
        </div>
      ) : (
        <Reasoning text={draftReasoning} />
      )}
    </Bubble>
  );
});

/** Bulle de relecture : suit une ligne de la table `transcripts`. La pensée brute
 * (`entry.thinking`) n'est jamais vide qu'une fois la partie scellée — le repli
 * `<details>` ci-dessous se déclenche donc sur la DONNÉE, pas sur `exposeThinking`
 * (qui régit le direct, pas l'archive une fois la partie terminée). */
export function EntryBubble({
  entry,
  lens,
  exposeThinking = false,
}: {
  entry: TranscriptEntry;
  lens?: GlassLens;
  exposeThinking?: boolean;
}) {
  void exposeThinking;
  const t = useT();
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
      {entry.thinking ? (
        <details className="mt-1">
          <summary className="cursor-pointer text-xs text-fg-faint transition-colors hover:text-fg-muted">
            {t("transcript.pensee-brute")}
          </summary>
          <div className="mt-2 border-l border-accent/50 pl-3 text-[13px] italic leading-relaxed text-fg-muted whitespace-pre-wrap">
            <ThinkAwareText text={entry.thinking} />
          </div>
        </details>
      ) : null}
    </Bubble>
  );
}
