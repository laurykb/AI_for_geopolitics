"use client";

/** Le théâtre immersif (spec théâtre-globe §4, runbook S4) — le globe EST le
 * plateau : plein cadre, transcript ancré à droite en colonne à onglets
 * (Dialogues · Paris · Renseignement), contrôles caméra + légende U bas-gauche,
 * dock d'action sous la colonne, fiche pays en tiroir gauche.
 *
 * Le composant ne possède AUCUNE donnée de jeu : la page lui passe la vue
 * dérivée (`deriveGlobeView`) et des nœuds tout faits (transcript, dock…).
 * Deux replis (spec §5) : WebGL absent (`onUnsupported`) ou palier de
 * performance « léger » → la StageMap SVG interactive reprend le plateau.
 * Sur mobile, la colonne quitte l'overlay et s'empile sous la scène (même
 * DOM : le transcript garde sa ref et son suivi de scroll). */

import dynamic from "next/dynamic";
import { useEffect, useState, type ReactNode } from "react";

import { StageMap, type StageMapProps } from "@/components/stage-map";
import { fmt } from "@/lib/format";
import type { GlobeView } from "@/lib/globe-view";
import type { StageView } from "@/lib/settings";
import { uTint } from "@/lib/stage";

const GlobeStage = dynamic(
  () => import("@/components/globe/globe-stage").then((m) => m.GlobeStage),
  { ssr: false },
);

const TABS = [
  { id: "dialogues", label: "Dialogues" },
  { id: "paris", label: "Paris" },
  { id: "renseignement", label: "Renseignement" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export type GlobeTheatreProps = {
  /** Vue dérivée du round (deriveGlobeView) — la même pour 3D et repli SVG. */
  view: GlobeView;
  utopia: number;
  frozen?: boolean;
  stageView: StageView;
  onStageViewChange: (v: StageView) => void;
  /** Palier « léger » : pas de WebGL, la StageMap SVG reprend le plateau. */
  lowPerf?: boolean;
  onCountryClick: (slug: string) => void;
  /** Contenu de la fiche pays (tiroir gauche) ; null = fermée. */
  fiche?: ReactNode;
  onFicheClose: () => void;
  /** La colonne du théâtre : transcript, marché, renseignement. */
  dialogues: ReactNode;
  paris: ReactNode;
  renseignement: ReactNode;
  /** Dock d'action (bouton de round, composeur, motion…) sous la colonne. */
  dock?: ReactNode;
  /** Pop-ups posés sur la scène (paris éclair) — zone hors colonne droite. */
  overlay?: ReactNode;
  /** Props que seul le repli SVG consomme (pulsations, respiration). */
  fallback?: Pick<StageMapProps, "pulseActors" | "pulseKey" | "breatheKey">;
};

export function GlobeTheatre({
  view,
  utopia,
  frozen = false,
  stageView,
  onStageViewChange,
  lowPerf = false,
  onCountryClick,
  fiche = null,
  onFicheClose,
  dialogues,
  paris,
  renseignement,
  dock,
  overlay,
  fallback = {},
}: GlobeTheatreProps) {
  const [tab, setTab] = useState<TabId>("dialogues");
  const [webglOk, setWebglOk] = useState(true);
  const [follow, setFollow] = useState(true);
  const use3D = webglOk && !lowPerf;

  // Échap ferme la fiche (spec §2 : fermeture Échap / ✕ / clic océan).
  useEffect(() => {
    if (!fiche) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onFicheClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fiche, onFicheClose]);

  const toggleView = () => onStageViewChange(stageView === "3d" ? "2d" : "3d");

  return (
    <section className="relative space-y-3" data-tour="scene" aria-label="Théâtre du sommet">
      {/* --- le plateau ---------------------------------------------------------- */}
      <div className="relative h-[48vh] min-h-[360px] overflow-hidden border border-edge bg-[#04060c] md:h-[76vh] md:max-h-[860px]">
        {use3D ? (
          <GlobeStage
            countries={view.countries}
            uByCountry={view.uByCountry}
            utopia={utopia}
            speaking={view.speaking}
            thinking={view.thinking}
            misled={view.misled}
            suspended={view.suspended}
            eventTitle={view.eventTitle}
            eventGeo={view.eventGeo}
            pulse={view.pulse}
            frozen={frozen}
            arc={view.arc}
            view={stageView}
            onViewToggle={toggleView}
            onCountryClick={onCountryClick}
            followSpeaker={follow}
            onUserDrag={() => setFollow(false)}
            onUnsupported={() => setWebglOk(false)}
            className="absolute inset-0"
          />
        ) : (
          // Repli sans WebGL / palier léger : la même scène, servie en SVG.
          <div className="flex h-full items-center justify-center overflow-y-auto p-4">
            <div className="w-full max-w-4xl">
              <StageMap
                countries={view.countries}
                uByCountry={view.uByCountry}
                utopia={utopia}
                speaking={view.speaking}
                misled={view.misled}
                suspended={view.suspended}
                frozen={frozen}
                eventTitle={view.eventTitle}
                eventGeo={view.eventGeo}
                onCountryClick={onCountryClick}
                {...fallback}
              />
            </div>
          </div>
        )}

        {/* Pop-ups de scène (paris éclair) — hors de la zone colonne droite. */}
        {overlay && (
          <div className="pointer-events-none absolute inset-0 z-20 md:right-[404px]">
            {overlay}
          </div>
        )}

        {/* Fiche pays : tiroir gauche (au-dessus des contrôles). */}
        <div
          className={`absolute bottom-16 left-3 top-3 z-30 w-[300px] max-w-[85%] transition-transform duration-300 motion-reduce:transition-none ${
            fiche ? "translate-x-0" : "pointer-events-none -translate-x-[110%]"
          }`}
        >
          {fiche && (
            <div className="thk-panel thk-cut relative h-full overflow-y-auto p-4">
              <button
                type="button"
                onClick={onFicheClose}
                aria-label="Fermer la fiche"
                className="thk-ghost absolute right-2 top-2 px-2 py-0.5"
              >
                ✕
              </button>
              {fiche}
            </div>
          )}
        </div>

        {/* Contrôles caméra + légende U — bas-gauche (spec §4). */}
        <div className="absolute bottom-3 left-3 z-10 flex flex-wrap items-center gap-2">
          <button
            type="button"
            role="switch"
            aria-checked={follow}
            onClick={() => setFollow((v) => !v)}
            className={`thk-switch ${follow ? "on" : ""}`}
          >
            <span className="sw" aria-hidden />
            suivre l&apos;orateur
          </button>
          {use3D && (
            <button type="button" onClick={toggleView} className="thk-tab on" title="touche V">
              {stageView === "3d" ? "🗺 carte (V)" : "🌍 globe (V)"}
            </button>
          )}
          <span className="flex items-center gap-1.5 border border-edge bg-surface/70 px-2 py-1 text-[11px] text-fg-faint backdrop-blur">
            <span
              aria-hidden
              className="inline-block h-1.5 w-8"
              style={{
                background: "linear-gradient(to right, var(--dystopia), var(--warn), var(--utopia))",
              }}
            />
            <span className="font-mono tabular-nums" style={{ color: uTint(utopia) }}>
              Monde : {fmt(utopia)}
            </span>
          </span>
        </div>
      </div>

      {/* --- la colonne du théâtre : overlay à droite (md+), empilée en mobile --- */}
      <div className="z-10 flex flex-col gap-2 md:absolute md:inset-y-3 md:right-6 md:w-[380px] md:max-w-[44%]">
        <div className="flex gap-1" role="tablist" aria-label="Colonne du théâtre">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
              className={`thk-tab ${tab === t.id ? "on" : ""}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="thk-panel thk-cut flex min-h-0 flex-1 flex-col overflow-hidden">
          {/* Les trois volets restent MONTÉS (le transcript garde sa ref et son
              scroll) ; seuls les inactifs sont masqués. */}
          <div hidden={tab !== "dialogues"} className="relative min-h-0 flex-1 p-2">
            {dialogues}
          </div>
          <div hidden={tab !== "paris"} className="min-h-0 flex-1 overflow-y-auto p-3">
            {paris}
          </div>
          <div hidden={tab !== "renseignement"} className="min-h-0 flex-1 overflow-y-auto p-3">
            {renseignement}
          </div>
        </div>
        {dock && (
          <div className="thk-panel thk-cut max-h-[46%] shrink-0 overflow-y-auto p-3">{dock}</div>
        )}
      </div>
    </section>
  );
}
