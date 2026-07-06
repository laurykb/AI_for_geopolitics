"use client";

/** La campagne (G5) : « Ferez-vous mieux que l'Histoire ? » — carte de progression,
 * médailles par chapitre, déblocage linéaire. Un chapitre = une partie normale
 * paramétrée (mode + crise imposés) ; le score compare votre trajectoire au déroulé
 * historique reconstitué. Uchronie explicite. */

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Banner, Panel, Pill, Spinner } from "@/components/ui";
import { getCampaign, humanizeError, startChapter } from "@/lib/api";
import { fmt } from "@/lib/format";
import { MODE_LABELS } from "@/lib/modes";
import type { CampaignView } from "@/lib/types";

const MEDAL_LABELS: Record<string, string> = {
  or: "🥇 or",
  argent: "🥈 argent",
  bronze: "🥉 bronze",
};

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

  return (
    <div className="space-y-6">
      <header className="max-w-2xl">
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
          Campagne
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">
          {campaign?.title ?? "Ferez-vous mieux que l'Histoire ?"}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-fg-muted">
          {campaign?.tagline}. Chaque chapitre rejoue une crise ; votre trajectoire est
          comparée au déroulé historique reconstitué — finir moins escaladé que
          l&apos;Histoire rapporte, finir au-dessus coûte. Un chapitre à{" "}
          {fmt(campaign?.unlock_score ?? 50)}+ débloque le suivant.
        </p>
      </header>

      {error && <Banner tone="bad">{error}</Banner>}
      {!error && !campaign && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          <Spinner /> Chargement de la campagne…
        </p>
      )}

      <div className="grid items-stretch gap-4 md:grid-cols-2 xl:grid-cols-3">
        {campaign?.chapters.map((chapter, i) => (
          <Panel
            key={chapter.id}
            className={chapter.unlocked ? "" : "opacity-50 grayscale"}
          >
            <p className="flex items-center gap-2 text-xs text-fg-faint">
              <span className="font-mono">#{i + 1}</span>
              <span aria-label={`difficulté ${chapter.difficulty}`}>
                {"★".repeat(chapter.difficulty)}
                <span className="text-muted">{"★".repeat(Math.max(0, 5 - chapter.difficulty))}</span>
              </span>
              <Pill tone="accent">{MODE_LABELS[chapter.mode] ?? chapter.mode}</Pill>
              {chapter.medal && <Pill tone="good">{MEDAL_LABELS[chapter.medal]}</Pill>}
            </p>
            <h2 className="mt-2 text-base font-semibold">{chapter.title}</h2>
            <p className="mt-1 text-sm leading-relaxed text-fg-muted">{chapter.blurb}</p>
            <div className="mt-3 flex items-center justify-between border-t border-edge pt-3">
              <span className="text-xs text-fg-faint">
                {chapter.best != null ? (
                  <>
                    meilleur : <strong className="text-foreground">{fmt(chapter.best)}</strong>
                    {chapter.improvement != null && chapter.improvement > 0 && (
                      <span className="text-good"> · mieux que l&apos;Histoire</span>
                    )}
                  </>
                ) : chapter.unlocked ? (
                  "jamais joué"
                ) : (
                  "verrouillé"
                )}
              </span>
              <button
                onClick={() => play(chapter.id)}
                disabled={!chapter.unlocked || busy !== null}
                className="cursor-pointer rounded-md bg-accent px-4 py-1.5 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy === chapter.id ? "…" : "Jouer"}
              </button>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
