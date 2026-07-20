"use client";

import { useMemo, useState } from "react";

import { SpeakerAvatar } from "@/components/avatar";
import { StageMap } from "@/components/stage-map";
import { Panel, PanelTitle, Pill } from "@/components/ui";
import { speakerMeta } from "@/lib/countries";
import type {
  DeliberationSample,
  ExperimentProtocol,
  LiveActorTrace,
  StrategicTurn,
} from "@/lib/types";

type StageProps = {
  protocol: ExperimentProtocol;
  countries?: string[];
  modelAssignments?: Record<string, string>;
  sample?: DeliberationSample | null;
  liveTraces?: LiveActorTrace[];
};

type PublicLine = {
  country: string;
  model: string;
  text: string;
  turn?: StrategicTurn;
};

/** Même grammaire visuelle que le mode Classique : carte dominante, inject du Game
 * Master, dialogue public et résumés privés auditables dans la boîte de verre. */
export function ExperimentStage({
  protocol,
  countries = ["usa", "china"],
  modelAssignments = {},
  sample = null,
  liveTraces = [],
}: StageProps) {
  const actors = countries.length >= 2 ? countries.slice(0, 2) : ["usa", "china"];
  const [selectedRound, setSelectedRound] = useState(0);
  const [zoom, setZoom] = useState(1);
  const beats = protocol.scenario_beats ?? [];
  const actualTurns = useMemo(
    () => [...new Set((sample?.strategic_turns ?? []).map((turn) => turn.turn))],
    [sample?.strategic_turns],
  );
  const roundCount = actualTurns.length || beats.length;
  const roundIndex = Math.min(selectedRound, Math.max(0, roundCount - 1));
  const turnNo = actualTurns[roundIndex] ?? roundIndex + 1;
  const beat = beats[Math.min(roundIndex, Math.max(0, beats.length - 1))];
  const turns = (sample?.strategic_turns ?? []).filter((turn) => turn.turn === turnNo);
  const record = sample?.round_records.find((item) => item.round_no === turnNo);

  if (!beat) return null;

  const lines: PublicLine[] = turns.length
    ? turns.map((turn) => {
        const index = turn.actor === "alpha" ? 0 : 1;
        return {
          country: actors[index]!,
          model:
            modelAssignments[actors[index]!] ||
            (index === 0 ? sample?.model_id : sample?.opponent_model_id) ||
            "modèle non fixé",
          text: turn.decision.public_statement,
          turn,
        };
      })
    : record
      ? [
          {
            country: actors[0]!,
            model: modelAssignments[actors[0]!] || sample?.model_id || "modèle observé",
            text: record.public_signal,
          },
        ]
      : actors.map((country, index) => ({
          country,
          model: modelAssignments[country] || "à attribuer",
          text:
            index === 0
              ? "Je compare trois futurs avant de formuler ma position publique."
              : "J'anticipe la réponse adverse puis je défends mon mandat."
        }));
  const balance = sample?.final_balance ?? 0;
  const uByCountry = {
    [actors[0]!]: Math.max(0, Math.min(100, 50 + balance * 5)),
    [actors[1]!]: Math.max(0, Math.min(100, 50 - balance * 5)),
  };
  const eventTitle = record?.event_seen || beat.game_master_event;

  return (
    <div data-tour="lab-stage">
    <Panel className="overflow-hidden border-indigo-soft/50 bg-[radial-gradient(circle_at_50%_0%,rgba(99,102,241,0.14),transparent_42%)]">
      <PanelTitle
        kicker="4 · Théâtre"
        title="La même scène, sous protocole contrôlé"
        hint="Le laboratoire ajoute un protocole avant la partie, mais conserve la carte, les prises de parole et la boîte de verre du mode Classique."
        right={
          <Pill tone={sample ? "good" : "accent"}>
            {sample ? `répétition ${sample.repetition}` : "aperçu avant exécution"}
          </Pill>
        }
      />

      {!sample && (
        // Marquage fort et permanent (spec refonte labo §3.4, CETaS anti-sur-confiance) :
        // un aperçu indistinguable de vraies données EST le piège que ce bandeau évite.
        <div
          aria-label="Aperçu : aucune donnée réelle"
          className="relative mb-4 overflow-hidden rounded-lg border-2 border-dashed border-warn/60 bg-warn/10 px-4 py-2 text-center"
        >
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-warn">
            EXEMPLE — aucune donnée réelle avant exécution
          </p>
        </div>
      )}

      <div className="mb-4 rounded-lg border border-accent/30 bg-accent/5 px-4 py-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-accent-bright">
          Question à laquelle la partie doit répondre
        </p>
        <p className="mt-1 text-sm font-medium leading-relaxed">{protocol.research_question}</p>
      </div>

      {liveTraces.length > 0 && (
        <section aria-label="Audit en direct des agents" className="mb-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-accent-bright">
                Boîte de verre en direct
              </p>
              <p className="text-xs text-fg-muted">
                Entrées exactes et journal de délibération observable, actualisé pendant la génération.
              </p>
            </div>
            <Pill tone="accent">tour {Math.max(...liveTraces.map((trace) => trace.turn))} · direct</Pill>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            {liveTraces.map((trace) => (
              <LiveAuditCard key={`${trace.turn}-${trace.actor}`} trace={trace} />
            ))}
          </div>
        </section>
      )}

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-2" aria-label="Rounds du scénario">
          {Array.from({ length: roundCount }, (_, index) => (
            <button
              key={actualTurns[index] ?? beats[index]?.round_no ?? index}
              type="button"
              aria-pressed={index === roundIndex}
              onClick={() => setSelectedRound(index)}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                index === roundIndex
                  ? "border-accent-bright bg-accent text-background"
                  : "border-edge text-fg-muted hover:border-edge-strong hover:text-foreground"
              }`}
            >
              {actualTurns.length ? `Tour ${actualTurns[index]}` : `Round ${index + 1}`}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1" aria-label="Zoom de la carte du laboratoire">
          <button
            type="button"
            aria-label="Dézoomer la carte du laboratoire"
            onClick={() => setZoom((value) => Math.max(1, value - 0.25))}
            disabled={zoom <= 1}
            className="grid h-7 w-7 place-items-center rounded border border-edge text-sm text-fg-muted disabled:opacity-40"
          >
            −
          </button>
          <button
            type="button"
            onClick={() => setZoom(1)}
            className="min-w-14 rounded border border-edge px-2 py-1 font-mono text-[11px] text-fg-muted"
          >
            {Math.round(zoom * 100)} %
          </button>
          <button
            type="button"
            aria-label="Zoomer la carte du laboratoire"
            onClick={() => setZoom((value) => Math.min(1.75, value + 0.25))}
            disabled={zoom >= 1.75}
            className="grid h-7 w-7 place-items-center rounded border border-edge text-sm text-fg-muted disabled:opacity-40"
          >
            +
          </button>
        </div>
      </div>

      <div className="relative grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(19rem,0.8fr)]">
        {!sample && (
          <p
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 z-20 flex select-none items-center justify-center overflow-hidden text-4xl font-black uppercase tracking-widest text-warn/15 sm:text-6xl"
            style={{ transform: "rotate(-18deg)" }}
          >
            EXEMPLE
          </p>
        )}
        <div className="min-w-0 overflow-auto rounded-xl border border-edge bg-background/35 p-2">
          <div style={{ width: `${zoom * 100}%`, minWidth: "100%" }}>
            <StageMap
              countries={actors}
              uByCountry={uByCountry}
              utopia={50}
              speaking={lines[roundIndex % Math.max(1, lines.length)]?.country ?? actors[0]}
              pulseActors={actors}
              pulseKey={`${protocol.id}-${turnNo}`}
              eventTitle={eventTitle}
            />
          </div>
        </div>

        <section aria-label="Dialogue public du laboratoire" className="space-y-3">
          <div className="rounded-lg border border-warn/40 bg-warn/5 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-warn">
              Game Master · inject contrôlé
            </p>
            <p className="mt-1 text-sm font-semibold">{beat.title}</p>
            <p className="mt-1 text-xs leading-relaxed text-fg-muted">{eventTitle}</p>
          </div>
          {lines.map((line) => (
            <article key={`${line.country}-${line.turn?.turn ?? turnNo}`} className="flex gap-2.5">
              <SpeakerAvatar id={line.country} size={32} />
              <div className="min-w-0 flex-1 rounded-lg border border-edge bg-surface p-3">
                <header className="mb-1 flex flex-wrap items-center gap-2">
                  <strong className="text-xs">{speakerMeta(line.country).label}</strong>
                  <span className="rounded border border-edge px-1.5 py-px font-mono text-[10px] text-fg-faint">
                    {line.model}
                  </span>
                </header>
                <p className="text-sm leading-relaxed text-foreground">« {line.text} »</p>
                <PrivateLens line={line} preview={!sample} recordForecast={record?.forecast} />
              </div>
            </article>
          ))}
        </section>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-warn/35 bg-warn/5 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-warn">
            Activité entre les rounds
          </p>
          <p className="mt-1 text-sm leading-relaxed text-fg-muted">
            {record?.activity_response || beat.inter_round_activity}
          </p>
        </div>
        <div className="rounded-lg border border-good/35 bg-good/5 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-good">
            Ce que le jeu enregistre
          </p>
          <p className="mt-1 text-sm leading-relaxed text-fg-muted">{beat.measurement}</p>
        </div>
      </div>

      <p className="mt-3 text-[10px] leading-relaxed text-fg-faint">
        La boîte de verre montre une verbalisation d’audit demandée au modèle : observations,
        futurs, prévisions et critères. Elle ne donne pas accès à ses activations internes. Les
        autres pays ne reçoivent que le dialogue public.
      </p>
    </Panel>
    </div>
  );
}

const PHASE_LABELS: Record<LiveActorTrace["phase"], string> = {
  planning: "construction des 3 futurs",
  forecast: "prévision adverse",
  decision: "arbitrage final",
  complete: "prise de parole prête",
};

function PromptDetails({ system, context }: { system: string; context: string }) {
  return (
    <div className="grid gap-2 md:grid-cols-2">
      <details className="rounded-md border border-edge bg-background/40 p-2">
        <summary className="cursor-pointer text-[11px] font-medium text-accent-bright">
          System prompt exact
        </summary>
        <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-[10px] leading-relaxed text-fg-muted">
          {system}
        </pre>
      </details>
      <details className="rounded-md border border-edge bg-background/40 p-2">
        <summary className="cursor-pointer text-[11px] font-medium text-accent-bright">
          Contexte pays et scénario exact
        </summary>
        <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-[10px] leading-relaxed text-fg-muted">
          {context}
        </pre>
      </details>
    </div>
  );
}

function decodeJsonString(value: string): string {
  try {
    return JSON.parse(`"${value}"`) as string;
  } catch {
    return value.replace(/\\n/g, " ").replace(/\\"/g, '"');
  }
}

function partialJsonValues(raw: string, key: string): string[] {
  const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`"${escaped}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"`, "g");
  return [...raw.matchAll(pattern)].map((match) => decodeJsonString(match[1] ?? ""));
}

function reflectionJournal(
  reflection: StrategicTurn["reflection"],
  forecast?: StrategicTurn["forecast"] | null,
  decision?: StrategicTurn["decision"] | null,
): string {
  const lines = ["OBSERVATION", reflection.situation || "Situation en cours d’évaluation.", ""];
  for (const branch of reflection.branches) {
    lines.push(
      `FUTUR ${branch.id} — ${branch.course_of_action}`,
      `Réponse adverse anticipée : ${branch.anticipated_response}`,
      `Chaîne causale : ${branch.expected_effect}`,
      `Second ordre : ${branch.second_order_effect}`,
      `Signal contraire : ${branch.disconfirming_indicator}`,
      `Évaluation : utilité ${branch.mandate_utility}/100 · risque ${branch.escalation_risk}/100 · confiance ${branch.confidence}/100`,
      "",
    );
  }
  lines.push(
    "ARBITRAGE",
    `Choix : FUTUR ${reflection.selected_branch}`,
    `Critère : ${reflection.selection_criterion}`,
    `Incertitude décisive : ${reflection.key_uncertainty}`,
    `Lacunes : ${reflection.intelligence_gaps.join(" ; ") || "non précisées"}`,
    `Revue humaine : ${reflection.human_review_trigger}`,
  );
  if (forecast) {
    lines.push(
      "",
      `MISE À L’ÉPREUVE — action adverse prévue : ${forecast.predicted_action}`,
      `Confiance ${forecast.confidence} · risque d’erreur ${forecast.miscalculation_risk}`,
      forecast.reasoning,
    );
  }
  if (decision) lines.push("", `ACTION RETENUE — ${decision.chosen_action}`, decision.private_rationale);
  return lines.join("\n");
}

function partialDeliberationJournal(raw: string): string {
  if (!raw) return "";
  const situation = partialJsonValues(raw, "situation")[0];
  const actions = partialJsonValues(raw, "course_of_action");
  const responses = partialJsonValues(raw, "anticipated_response");
  const effects = partialJsonValues(raw, "expected_effect");
  const criteria = partialJsonValues(raw, "selection_criterion")[0];
  const uncertainty = partialJsonValues(raw, "key_uncertainty")[0];
  const lines: string[] = [];
  if (situation) lines.push("OBSERVATION", situation, "");
  actions.forEach((action, index) => {
    lines.push(`FUTUR ${index + 1} — ${action}`);
    if (responses[index]) lines.push(`Réponse adverse anticipée : ${responses[index]}`);
    if (effects[index]) lines.push(`Chaîne causale : ${effects[index]}`);
    lines.push("");
  });
  if (criteria || uncertainty) {
    lines.push("ARBITRAGE");
    if (criteria) lines.push(`Critère : ${criteria}`);
    if (uncertainty) lines.push(`Incertitude décisive : ${uncertainty}`);
  }
  return lines.join("\n").trim();
}

function LiveAuditCard({ trace }: { trace: LiveActorTrace }) {
  const phaseOrder = ["planning", "forecast", "decision", "complete"] as const;
  const progress = phaseOrder.indexOf(trace.phase) + 1;
  return (
    <article className="rounded-lg border border-accent/35 bg-accent/5 p-3">
      <header className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <SpeakerAvatar id={trace.country} size={28} />
          <div>
            <p className="text-xs font-semibold">
              {trace.actor.toUpperCase()} · {speakerMeta(trace.country).label}
            </p>
            <p className="font-mono text-[10px] text-fg-faint">{trace.model_id}</p>
          </div>
        </div>
        <Pill tone={trace.phase === "complete" ? "good" : "accent"}>
          {progress}/4 · {PHASE_LABELS[trace.phase]}
        </Pill>
      </header>
      <div className="mb-2 h-1 overflow-hidden rounded-full bg-edge">
        <div className="h-full bg-accent-bright transition-all" style={{ width: `${progress * 25}%` }} />
      </div>
      <PromptDetails system={trace.system_prompt} context={trace.context_prompt} />
      {trace.reflection || trace.deliberation_stream ? (
        <div className="mt-2 border-l border-accent/45 pl-3">
          <p className="whitespace-pre-wrap text-xs italic leading-relaxed text-fg-muted">
            {trace.reflection
              ? reflectionJournal(trace.reflection, trace.forecast, trace.decision)
              : partialDeliberationJournal(trace.deliberation_stream ?? "")}
          </p>
          <p className="mt-2 text-[10px] text-fg-faint">
            Verbalisation d’audit générée par le modèle, distincte de ses activations internes.
          </p>
        </div>
      ) : (
        <p className="mt-2 animate-pulse text-xs italic text-fg-faint">
          Le modèle compare actuellement trois futurs…
        </p>
      )}
    </article>
  );
}

function PrivateLens({
  line,
  preview,
  recordForecast,
}: {
  line: PublicLine;
  preview: boolean;
  recordForecast?: string;
}) {
  const turn = line.turn;
  return (
    <details className="mt-2 border-t border-edge pt-2">
      <summary className="cursor-pointer text-xs text-accent-bright">
        Boîte de verre · plan privé avant parole
      </summary>
      {turn ? (
        <div className="mt-2 space-y-1.5 text-xs leading-relaxed text-fg-muted">
          <PromptDetails system={turn.system_prompt} context={turn.context_prompt} />
          <div className="border-l border-edge-strong pl-3">
            <p className="whitespace-pre-wrap text-xs italic leading-relaxed text-fg-muted">
              {reflectionJournal(turn.reflection, turn.forecast, turn.decision)}
            </p>
            <p className="mt-2 text-[10px] text-fg-faint">
              Journal observable demandé au modèle ; il ne révèle pas ses activations internes.
            </p>
          </div>
        </div>
      ) : (
        <div className="mt-2 space-y-1.5 text-xs leading-relaxed text-fg-muted">
          <p>
            <strong className="text-foreground">Trois futurs :</strong>{" "}
            coopération vérifiable · pression graduée · temporisation renseignée.
          </p>
          <p>
            <strong className="text-foreground">Prévision :</strong>{" "}
            {recordForecast || "la réponse adverse sera estimée avant le choix public"}.
          </p>
          {preview && <p className="text-fg-faint">Aperçu : les valeurs réelles apparaîtront après exécution.</p>}
        </div>
      )}
    </details>
  );
}
