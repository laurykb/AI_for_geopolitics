"use client";

/** Salle des observables (RG-4), extraite du théâtre.
 *
 * Le JEU reste en façade — le Dossier (console d'ACHATS du joueur, outil de
 * détection) et « La table » (les suspects, en vue réduite). Le MOTEUR —
 * « Renseignement » (détection fine G18-G23) et « Le monde » (jauges
 * risque/escalade/trajectoire/traités détaillées) — ne s'affiche qu'en Expert
 * (`showEngine`) ; il est expliqué dans l'onglet Informations. Rien n'est
 * supprimé : tout est routé. */

import type { LiveRound } from "@/hooks/useRoundStream";
import { CountryTable, type CountrySnapshot } from "@/components/country-table";
import { IntelPanel } from "@/components/intel";
import {
  ParticipationPanel,
  PowerSeekingPanel,
  PromisePanel,
  RiskPanel,
  SignalGapPanel,
} from "@/components/observables";
import { LadderPanel } from "@/components/modes";
import { TabGroup } from "@/components/observatory";
import { useT } from "@/components/settings-provider";
import { TrajectoryPanel } from "@/components/trajectory";
import { TreatiesPanel } from "@/components/treaties";
import { Panel, PanelTitle } from "@/components/ui";
import { tableDetailedByDefault } from "@/lib/density";
import type { SignalGapView } from "@/lib/signal";
import type {
  GameDetail,
  PromiseView,
  TrajectoryState,
  TreatiesUpdate,
} from "@/lib/types";

export function ObservablesGrid({
  gameId,
  detail,
  round,
  summit,
  fogOn,
  streaming,
  showEngine,
  worldCountries,
  signalGaps,
  promiseRegistry,
  trajectory,
  uHistory,
  treatiesUpdate,
  onSpent,
}: {
  gameId: string;
  detail: GameDetail | null;
  round: LiveRound;
  summit: string[];
  fogOn: boolean;
  streaming: boolean;
  showEngine: boolean;
  worldCountries: Record<string, CountrySnapshot> | null;
  signalGaps: Record<string, SignalGapView> | null;
  promiseRegistry: PromiseView[] | null;
  trajectory: TrajectoryState | undefined;
  uHistory: number[];
  treatiesUpdate: TreatiesUpdate | undefined;
  onSpent: () => void;
}) {
  const t = useT();
  return (
    <div className={`grid items-start gap-4 ${showEngine ? "lg:grid-cols-2" : ""}`}>
      {detail?.live && detail.status === "running" && (
        <IntelPanel
          gameId={gameId}
          countries={summit}
          fog={fogOn}
          playAs={detail.play_as}
          claims={round.turns
            .filter((t) => t.done && t.model !== "humain" && t.text)
            .map((t) => [t.country, t.text] as [string, string])}
          streaming={streaming}
          onSpent={onSpent}
        />
      )}
      {showEngine && (
        <>
          <TabGroup
            label={t("obs.renseignement")}
            hint={t("obs.renseignement-aide")}
            dataTour="renseignement"
            empty={
              detail?.live && detail.status === "running" ? (
                <Panel>
                  <p className="text-sm text-fg-muted">{t("obs.renseignement-vide")}</p>
                </Panel>
              ) : undefined
            }
            tabs={[
              {
                key: "signal",
                label: t("obs.tab.signal"),
                content: signalGaps ? <SignalGapPanel gaps={signalGaps} /> : null,
              },
              {
                key: "promesses",
                label: t("obs.tab.promesses"),
                content:
                  promiseRegistry && promiseRegistry.length > 0 ? (
                    <PromisePanel
                      registry={promiseRegistry}
                      finished={detail?.status === "finished"}
                    />
                  ) : null,
              },
              {
                key: "surveillance",
                label: t("obs.tab.surveillance"),
                content: round.powerSeeking ? (
                  <PowerSeekingPanel scores={round.powerSeeking} />
                ) : null,
              },
            ]}
          />
          <TabGroup
            label={t("obs.monde")}
            tabs={[
              {
                key: "trajectoire",
                label: t("obs.tab.trajectoire"),
                content: trajectory ? (
                  <TrajectoryPanel state={trajectory} history={uHistory} />
                ) : null,
              },
              {
                key: "risque",
                label: t("obs.tab.risque"),
                content: round.risk ? <RiskPanel risk={round.risk} /> : null,
              },
              {
                key: "tension",
                label: t("obs.tab.tension"),
                content: round.ladder ? <LadderPanel ladder={round.ladder} /> : null,
              },
              {
                key: "traites",
                label: t("obs.tab.traites"),
                content: treatiesUpdate ? <TreatiesPanel update={treatiesUpdate} /> : null,
              },
            ]}
          />
        </>
      )}
      <TabGroup
        label={t("obs.table")}
        tabs={[
          {
            key: "pays",
            label: t("obs.tab.pays"),
            content: worldCountries ? (
              <Panel>
                <PanelTitle
                  kicker="États"
                  title="État des pays"
                  hint="Photo vivante du monde — les chiffres bougent avec les verdicts du juge, bornés par les règles du jeu. Ta ligne est en tête. En mode Chaotique, tu ne vois que ce que ton pays croit."
                  right={
                    <a
                      href="/informations"
                      className="text-xs text-fg-faint underline transition-colors hover:text-fg-muted"
                    >
                      d&apos;où viennent ces chiffres ?
                    </a>
                  }
                />
                <CountryTable
                  worldCountries={worldCountries}
                  postures={round.postures ?? detail?.postures}
                  history={detail?.index_history}
                  playAs={detail?.play_as}
                  defaultDetailed={tableDetailedByDefault(detail?.difficulty)}
                  modelAssignments={detail?.model_cast?.assignments}
                />
              </Panel>
            ) : null,
          },
          {
            // RG-4 — la participation détaillée est du MOTEUR : Expert seulement.
            // La vue « pays » (les suspects) reste, elle, en façade.
            key: "parole",
            label: t("obs.tab.parole"),
            content:
              showEngine && round.participation ? (
                <ParticipationPanel
                  spoke={round.participation.spoke}
                  silent={round.participation.silent}
                />
              ) : null,
          },
        ]}
      />
    </div>
  );
}
