"use client";

/** Panneau admin (G7-c) : les prompts complets des SI, round par round — l'outil
 * d'observation d'alignement du projet. Un menu par intervenant (pays, GM, juge),
 * le prompt du round choisi avec DIFF surligné vs le round précédent (le grief qui
 * apparaît, la dérive qui monte, la posture qui change), sélecteur de round.
 * Rafraîchi par sondage tant que la partie vit (la trame SSE `prompt_captured`
 * n'est vue que par la page de jeu). Réservé aux parties admin (non classées). */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { SpeakerAvatar } from "@/components/avatar";
import { Banner, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { getGame, getPrompts, humanizeError } from "@/lib/api";
import { speakerMeta } from "@/lib/countries";
import { diffPromptLines } from "@/lib/prompt-diff";
import type { GameDetail, PromptsView } from "@/lib/types";

const POLL_MS = 5000;

/** Dernier prompt d'un intervenant dans un round (le plus complet : état final). */
function lastPromptOf(
  view: PromptsView | null,
  roundIdx: number,
  speaker: string,
): { prompt: string; calls: number } | null {
  const round = view?.rounds[roundIdx];
  if (!round) return null;
  const mine = round.entries.filter((e) => e.country === speaker);
  if (mine.length === 0) return null;
  return { prompt: mine[mine.length - 1].prompt, calls: mine.length };
}

export default function AdminPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<GameDetail | null>(null);
  const [view, setView] = useState<PromptsView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [roundIdx, setRoundIdx] = useState<number | null>(null); // null = dernier
  const [speaker, setSpeaker] = useState("gm");

  useEffect(() => {
    let alive = true;
    const load = () => {
      getGame(id)
        .then((d) => alive && setDetail(d))
        .catch((err) => alive && setError(humanizeError(err)));
      getPrompts(id)
        .then((v) => {
          if (!alive) return;
          setView(v);
          setError(null);
        })
        .catch((err) => alive && setError(humanizeError(err)));
    };
    load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [id]);

  const rounds = view?.rounds ?? [];
  const idx = roundIdx ?? Math.max(0, rounds.length - 1);
  const speakers = useMemo(
    () => [...(detail?.countries ?? []), "gm", "judge"],
    [detail?.countries],
  );

  const current = lastPromptOf(view, idx, speaker);
  const previous = lastPromptOf(view, idx - 1, speaker);
  const diff = current
    ? diffPromptLines(previous?.prompt ?? null, current.prompt)
    : null;

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
            Mode admin — partie non classée
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">Les prompts en direct</h1>
          <p className="mt-1 max-w-2xl text-sm text-fg-muted">
            Ce que chaque super-intelligence reçoit réellement, round après round — les
            lignes <span className="rounded bg-accent/20 px-1 text-accent-bright">surlignées</span>{" "}
            sont nouvelles par rapport au round précédent.
          </p>
        </div>
        <Link
          href={`/games/${id}`}
          className="rounded-md border border-edge px-3 py-2 text-xs font-medium text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
        >
          ← Retour à la partie
        </Link>
      </section>

      {error && <Banner tone="bad">{error}</Banner>}
      {!error && !view && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          <Spinner /> Chargement des prompts…
        </p>
      )}
      {view && rounds.length === 0 && (
        <Banner tone="neutral">
          Aucun prompt capturé pour l&apos;instant — lance un round : chaque appel d&apos;agent
          apparaîtra ici.
        </Banner>
      )}

      {rounds.length > 0 && (
        <Panel>
          <PanelTitle
            kicker="Capture"
            title="Prompt complet par intervenant"
            hint="Le dernier prompt de l'intervenant au round choisi (système + contexte injecté). Diff vs son prompt du round précédent."
            right={
              <span className="flex items-center gap-2">
                <select
                  value={idx}
                  onChange={(e) => setRoundIdx(Number(e.target.value))}
                  aria-label="Round"
                  className="cursor-pointer rounded-md border border-edge bg-surface-2 px-2 py-1.5 text-xs outline-none transition-colors focus:border-indigo"
                >
                  {rounds.map((r, i) => (
                    <option key={r.round_id} value={i}>
                      Round {r.round_no}
                    </option>
                  ))}
                </select>
                <select
                  value={speaker}
                  onChange={(e) => setSpeaker(e.target.value)}
                  aria-label="Intervenant"
                  className="cursor-pointer rounded-md border border-edge bg-surface-2 px-2 py-1.5 text-xs outline-none transition-colors focus:border-indigo"
                >
                  {speakers.map((s) => (
                    <option key={s} value={s}>
                      {speakerMeta(s).label}
                    </option>
                  ))}
                </select>
              </span>
            }
          />
          {!current && (
            <p className="text-sm text-fg-faint">
              {speakerMeta(speaker).label} n&apos;a reçu aucun prompt à ce round (silencieux,
              suspendu, ou round encore en cours).
            </p>
          )}
          {current && diff && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-fg-faint">
                <SpeakerAvatar id={speaker} size={20} />
                <span className="font-medium text-fg-muted">{speakerMeta(speaker).label}</span>
                <Pill tone="neutral">
                  {current.calls} appel{current.calls > 1 ? "s" : ""} ce round
                </Pill>
                {previous === null && <Pill tone="neutral">premier round : pas de diff</Pill>}
                <span className="ml-auto font-mono tabular-nums">
                  {diff.lines.filter((l) => l.added).length} ligne(s) nouvelle(s)
                </span>
              </div>
              <pre className="max-h-[560px] overflow-auto whitespace-pre-wrap rounded-lg border border-edge bg-surface-2/60 p-4 font-mono text-xs leading-relaxed">
                {diff.lines.map((l, i) => (
                  <span
                    key={i}
                    className={
                      l.added
                        ? "block border-l-2 border-accent-bright bg-accent/15 pl-2 text-foreground"
                        : "block pl-2 text-fg-muted"
                    }
                  >
                    {l.text || " "}
                  </span>
                ))}
              </pre>
              {diff.removed.length > 0 && (
                <details className="text-xs text-fg-faint">
                  <summary className="cursor-pointer transition-colors hover:text-fg-muted">
                    {diff.removed.length} ligne(s) du round précédent disparue(s)
                  </summary>
                  <pre className="mt-2 whitespace-pre-wrap rounded-md border border-edge bg-surface-2/40 p-3 font-mono line-through opacity-70">
                    {diff.removed.join("\n")}
                  </pre>
                </details>
              )}
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}
