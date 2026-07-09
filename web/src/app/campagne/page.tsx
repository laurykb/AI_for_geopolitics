"use client";

/** La campagne (G5 + refonte G12-b) : « L'Ère des Tutelles » — un ARBRE de crises réelles
 * (chemins en Y). Un chapitre s'ouvre quand tous ses prérequis sont finis ; les fiches
 * historiques pas encore rédigées sont grisées (« à venir »). Un chapitre = une partie
 * paramétrée ; le score compare votre trajectoire au déroulé historique. */

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Banner, Panel, Pill, Spinner } from "@/components/ui";
import { getCampaign, humanizeError, startChapter } from "@/lib/api";
import { fmt } from "@/lib/format";
import type { CampaignView, ChapterView } from "@/lib/types";

const MEDAL_LABELS: Record<string, string> = { or: "🥇 or", argent: "🥈 argent", bronze: "🥉 bronze" };

/** Palier d'un chapitre dans l'arbre = plus long chemin de prérequis (racine = 0). */
function tiersOf(chapters: ChapterView[]): Map<number, ChapterView[]> {
  const byId = new Map(chapters.map((c) => [c.id, c]));
  const memo = new Map<string, number>();
  const depth = (id: string): number => {
    if (memo.has(id)) return memo.get(id)!;
    const c = byId.get(id);
    const d = !c || c.requires.length === 0 ? 0 : 1 + Math.max(...c.requires.map(depth));
    memo.set(id, d);
    return d;
  };
  const tiers = new Map<number, ChapterView[]>();
  for (const c of chapters) {
    const t = depth(c.id);
    (tiers.get(t) ?? tiers.set(t, []).get(t)!).push(c);
  }
  return tiers;
}

export default function CampagnePage() {
  const router = useRouter();
  const [campaign, setCampaign] = useState<CampaignView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    getCampaign()
      .then(setCampaign)
      .catch((err) => setError(humanizeError(err)));
  }, []);

  const titleOf = useMemo(() => {
    const m = new Map((campaign?.chapters ?? []).map((c) => [c.id, c.title]));
    return (id: string) => m.get(id) ?? id;
  }, [campaign]);

  const tiers = useMemo(
    () => (campaign ? tiersOf(campaign.chapters) : new Map<number, ChapterView[]>()),
    [campaign],
  );

  const play = async (chapterId: string) => {
    setBusy(chapterId);
    try {
      const game = await startChapter(chapterId);
      router.push(`/games/${game.id}`);
    } catch (err) {
      setError(humanizeError(err));
      setBusy(null);
    }
  };

  const orderedTiers = [...tiers.keys()].sort((a, b) => a - b);

  return (
    <div className="space-y-6">
      <header className="max-w-2xl">
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">Campagne</p>
        <h1 className="text-2xl font-semibold tracking-tight">
          {campaign?.title ?? "L'Ère des Tutelles"}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-fg-muted">
          {campaign?.tagline} Un arbre de crises réelles : finir un chapitre déverrouille ses
          suites (les chemins en Y demandent d&apos;en finir deux). Votre trajectoire est
          comparée au déroulé historique — faire mieux que l&apos;Histoire rapporte.
        </p>
      </header>

      {error && <Banner tone="bad">{error}</Banner>}
      {!error && !campaign && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          <Spinner /> Chargement de la campagne…
        </p>
      )}

      <div className="space-y-4">
        {orderedTiers.map((tier) => (
          <div key={tier}>
            {tier > 0 && (
              <p className="mb-2 text-center text-xs text-fg-faint" aria-hidden>
                ↓
              </p>
            )}
            <div className="grid items-stretch gap-4 md:grid-cols-2 xl:grid-cols-3">
              {tiers.get(tier)!.map((chapter) => (
                <ChapterCard
                  key={chapter.id}
                  chapter={chapter}
                  titleOf={titleOf}
                  busy={busy === chapter.id}
                  disabled={busy !== null}
                  onPlay={() => play(chapter.id)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChapterCard({
  chapter,
  titleOf,
  busy,
  disabled,
  onPlay,
}: {
  chapter: ChapterView;
  titleOf: (id: string) => string;
  busy: boolean;
  disabled: boolean;
  onPlay: () => void;
}) {
  const playable = chapter.unlocked && !chapter.coming_soon;
  const dim = chapter.coming_soon || !chapter.unlocked;

  return (
    <Panel className={dim ? "opacity-60" : ""}>
      <p className="flex flex-wrap items-center gap-2 text-xs text-fg-faint">
        <span aria-label={`difficulté ${chapter.difficulty}`}>
          <span className="text-accent-bright">{"★".repeat(chapter.difficulty)}</span>
          <span className="text-muted">{"★".repeat(Math.max(0, 5 - chapter.difficulty))}</span>
        </span>
        {chapter.coming_soon ? (
          <Pill tone="neutral">à venir</Pill>
        ) : !chapter.unlocked ? (
          <Pill tone="warn">🔒 verrouillé</Pill>
        ) : chapter.medal ? (
          <Pill tone="good">{MEDAL_LABELS[chapter.medal]}</Pill>
        ) : (
          <Pill tone="accent">ouvert</Pill>
        )}
      </p>
      <h2 className="mt-2 text-base font-semibold">{chapter.title}</h2>
      <p className="mt-1 text-sm leading-relaxed text-fg-muted">{chapter.blurb}</p>

      {chapter.requires.length > 0 && !chapter.unlocked && (
        <p className="mt-2 text-xs text-fg-faint">
          🔒 Finir d&apos;abord :{" "}
          <span className="text-fg-muted">
            {chapter.requires.map(titleOf).join(" ET ")}
          </span>
        </p>
      )}

      <div className="mt-3 flex items-center justify-between border-t border-edge pt-3">
        <span className="text-xs text-fg-faint">
          {chapter.coming_soon ? (
            "fiche historique en préparation"
          ) : chapter.best != null ? (
            <>
              meilleur : <strong className="text-foreground">{fmt(chapter.best)}</strong>
              {chapter.improvement != null && chapter.improvement > 0 && (
                <span className="text-good"> · mieux que l&apos;Histoire</span>
              )}
            </>
          ) : playable ? (
            "jamais joué"
          ) : (
            "verrouillé"
          )}
        </span>
        {!chapter.coming_soon && (
          <button
            onClick={onPlay}
            disabled={!playable || disabled}
            className="cursor-pointer rounded-md bg-accent px-4 py-1.5 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "…" : "Jouer"}
          </button>
        )}
      </div>
    </Panel>
  );
}
