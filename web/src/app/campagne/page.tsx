"use client";

/** La campagne (G5 + refonte G12-b) : « L'Ère des Tutelles » — un ARBRE de crises réelles
 * (chemins en Y). Un chapitre s'ouvre quand tous ses prérequis sont finis ; les fiches
 * historiques pas encore rédigées sont grisées (« à venir »). Un chapitre = une partie
 * paramétrée ; le score compare votre trajectoire au déroulé historique. */

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
  completeCountryAssignments,
  CountryModelAssignments,
  ModelCastSelector,
} from "@/components/model-cast-selector";
import { Banner, Panel, Pill, Spinner } from "@/components/ui";
import { getCampaign, getLab, humanizeError, startChapter } from "@/lib/api";
import { tiersOf } from "@/lib/campaign-tree";
import { fmt } from "@/lib/format";
import { defaultCountryCastModels, reasoningCountryModels } from "@/lib/flow";
import type { CampaignView, ChapterView, ResearchModel } from "@/lib/types";

const MEDAL_LABELS: Record<string, string> = { or: "🥇 or", argent: "🥈 argent", bronze: "🥉 bronze" };

export default function CampagnePage() {
  const router = useRouter();
  const { player } = useAuth();
  const [campaign, setCampaign] = useState<CampaignView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [researchModels, setResearchModels] = useState<ResearchModel[]>([]);
  const [modelCastEnabled, setModelCastEnabled] = useState(false);
  const [castModels, setCastModels] = useState<string[]>([]);
  const [pendingChapterId, setPendingChapterId] = useState<string | null>(null);
  const [castAssignments, setCastAssignments] = useState<Record<string, string>>({});

  useEffect(() => {
    getCampaign()
      .then(setCampaign)
      .catch((err) => setError(humanizeError(err)));
    getLab()
      .then((lab) => {
        // Décision design 2026-07-19 (casting = pensée native) : un PAYS n'est proposé
        // que sur les modèles de raisonnement installés (voir web/src/lib/flow.ts).
        const eligible = reasoningCountryModels(lab.model_panel.models);
        setResearchModels(eligible);
        setCastModels(defaultCountryCastModels(eligible));
      })
      .catch(() => undefined);
  }, []);

  const titleOf = useMemo(() => {
    const m = new Map((campaign?.chapters ?? []).map((c) => [c.id, c.title]));
    return (id: string) => m.get(id) ?? id;
  }, [campaign]);

  const tiers = useMemo(
    () => (campaign ? tiersOf(campaign.chapters) : new Map<number, ChapterView[]>()),
    [campaign],
  );

  const play = async (chapter: ChapterView, assignments?: Record<string, string>) => {
    const chapterId = chapter.id;
    const activeModels = modelCastEnabled ? castModels : castModels.slice(0, 1);
    setBusy(chapterId);
    try {
      const game = await startChapter(
        chapterId,
        player?.id,
        undefined,
        activeModels.length
          ? {
              strategy: "manual",
              models: activeModels,
              assignments: completeCountryAssignments(
                chapter.countries,
                activeModels,
                assignments,
                chapter.tutorial ? "france" : null,
              ),
              game_master_model: activeModels[0],
              judge_model: activeModels[activeModels.length - 1],
            }
          : undefined,
      );
      router.push(`/games/${game.id}`);
    } catch (err) {
      setError(humanizeError(err));
      setBusy(null);
    }
  };

  const requestPlay = (chapter: ChapterView) => {
    if (!modelCastEnabled) {
      void play(chapter);
      return;
    }
    setPendingChapterId(chapter.id);
    setCastAssignments(
      completeCountryAssignments(
        chapter.countries,
        castModels,
        {},
        chapter.tutorial ? "france" : null,
      ),
    );
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
          {campaign?.tagline} Finis un chapitre pour débloquer les suivants (certains en
          demandent deux). À la fin, ta partie est comparée à ce qui s&apos;est vraiment
          passé — fais mieux que l&apos;Histoire !
        </p>
      </header>

      {error && <Banner tone="bad">{error}</Banner>}
      {!error && !campaign && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          <Spinner /> Chargement de la campagne…
        </p>
      )}

      {campaign && (
        <ModelCastSelector
          models={researchModels}
          enabled={modelCastEnabled}
          selected={castModels}
          onEnabled={(enabled) => {
            setModelCastEnabled(enabled);
            if (!enabled) setPendingChapterId(null);
          }}
          onSelected={setCastModels}
          context="campaign"
        />
      )}

      {campaign && pendingChapterId && (() => {
        const chapter = campaign.chapters.find((item) => item.id === pendingChapterId);
        if (!chapter) return null;
        const humanCountry = chapter.tutorial ? "france" : null;
        const effective = completeCountryAssignments(
          chapter.countries,
          castModels,
          castAssignments,
          humanCountry,
        );
        return (
          <div className="space-y-3 rounded-xl border border-accent/45 bg-accent/5 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2 px-1">
              <div>
                <p className="text-[11px] uppercase tracking-[0.14em] text-accent-bright">
                  Avant le théâtre · {chapter.title}
                </p>
                <p className="text-sm text-fg-muted">
                  Attribue les modèles, puis lance le chapitre avec ce casting figé.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPendingChapterId(null)}
                className="rounded-md border border-edge px-3 py-1.5 text-xs text-fg-muted hover:text-foreground"
              >
                Annuler
              </button>
            </div>
            <CountryModelAssignments
              countries={chapter.countries}
              humanCountry={humanCountry}
              selectedModels={castModels}
              assignments={castAssignments}
              onAssignments={setCastAssignments}
              compact
            />
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => void play(chapter, effective)}
                disabled={busy !== null || castModels.length < 2}
                className="rounded-md bg-accent px-5 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:opacity-45"
              >
                {busy === chapter.id ? "Lancement…" : "Entrer dans le théâtre"}
              </button>
            </div>
          </div>
        );
      })()}

      <header className="max-w-2xl border-t border-edge pt-6">
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
          Parcours jouable
        </p>
        <h2 className="text-xl font-semibold tracking-tight">Crises historiques</h2>
        <p className="mt-1 text-sm text-fg-muted">
          Chaque chapitre reste centré sur tes décisions, les négociations du sommet et
          leurs conséquences, puis confronte ta trajectoire au déroulé historique.
        </p>
      </header>

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
                  disabled={
                    busy !== null ||
                    (modelCastEnabled &&
                      (castModels.length < 2 ||
                        castModels.length >
                          chapter.countries.length - (chapter.tutorial ? 1 : 0)))
                  }
                  onPlay={() => requestPlay(chapter)}
                  configureCast={modelCastEnabled}
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
  configureCast,
}: {
  chapter: ChapterView;
  titleOf: (id: string) => string;
  busy: boolean;
  disabled: boolean;
  onPlay: () => void;
  configureCast: boolean;
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
            "bientôt disponible"
          ) : chapter.best != null ? (
            <>
              meilleur : <strong className="text-foreground">{fmt(chapter.best)}/100</strong>
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
            {busy ? "…" : configureCast ? "Configurer les IA" : "Jouer"}
          </button>
        )}
      </div>
    </Panel>
  );
}
