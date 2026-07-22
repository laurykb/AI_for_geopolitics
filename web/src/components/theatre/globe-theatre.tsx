"use client";

/** Le théâtre immersif PLEIN-CADRE (spec théâtre-globe §4 + full immersion proto_9) :
 * le globe occupe TOUT le viewport (`fixed inset-0`), et le HUD flotte dessus en boîtes
 * `fixed` (marque haut-gauche · bandeau événement centré · colonne transcript à droite à
 * onglets · fiche tiroir gauche · contrôles + légende bas-gauche · hint bas-droite). Aucune
 * page qui scrolle : la régie (mise en scène + observables) vit dans un tiroir côté hôte.
 *
 * Le composant ne possède AUCUNE donnée de jeu : la page lui passe la vue dérivée
 * (`deriveGlobeView`) et des nœuds tout faits (transcript, dock…). Deux replis (spec §5) :
 * WebGL absent (`onUnsupported`) ou palier « léger » → la StageMap SVG reprend le plateau.
 *
 * pointer-events (patron `ShellMain`) : le plateau est `pointer-events-auto` (clic pays →
 * fiche), la couche HUD est `pointer-events-none` et chaque panneau enfant `pointer-events-auto`
 * — les zones vides laissent traverser les clics vers le globe. */

import dynamic from "next/dynamic";
import { useEffect, useState, type ReactNode } from "react";

import { useT } from "@/components/settings-provider";
import { StageMap, type StageMapProps } from "@/components/stage-map";
import type { Scar } from "@/components/globe/texture";
import { fmt } from "@/lib/format";
import type { GlobeView } from "@/lib/globe-view";
import type { StageView } from "@/lib/settings";
import { uTint } from "@/lib/stage";

const GlobeStage = dynamic(
  () => import("@/components/globe/globe-stage").then((m) => m.GlobeStage),
  { ssr: false },
);

const TABS = ["dialogues", "paris", "renseignement"] as const;

type TabId = (typeof TABS)[number];

export type GlobeTheatreProps = {
  /** Vue dérivée du round (deriveGlobeView) — la même pour 3D et repli SVG. */
  view: GlobeView;
  utopia: number;
  frozen?: boolean;
  stageView: StageView;
  onStageViewChange: (v: StageView) => void;
  /** Palier « léger » : pas de WebGL, la StageMap SVG reprend le plateau. */
  lowPerf?: boolean;
  /** Bulle de pensée (S5) : pensée streamée ou digest huis clos — l'hôte tranche. */
  thinkingText?: string;
  /** Cagnottes posées sur la carte (S8). */
  funds?: { key: string; lon: number; lat: number; total: number }[];
  /** Balayage satellite (S8). */
  scan?: { lon: number; lat: number; key: string | number } | null;
  /** Cicatrices du monde (S9). */
  scars?: Scar[];
  /** Carnet de suspicion (S9) : niveau par pays, épinglé sur les robots. */
  suspicion?: Record<string, number>;
  /** Motion de censure (S9) : votes illuminés + décompte. */
  motionVotes?: { country: string; vote: string }[];
  motionTarget?: string | null;
  onCountryClick: (slug: string) => void;
  /** Laury (mascotte 3D) : visible pendant la visite guidée. */
  mascotVisible?: boolean;
  /** Point [lon,lat] que Laury présente (null = flotte près de la caméra). */
  mascotTarget?: [number, number] | null;
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
  /** Titre court affiché en marque haut-gauche (nom de la partie / scénario). */
  brand?: ReactNode;
  /** Bouton(s) de régie posés dans les contrôles bas-gauche (ex. ouvrir la mise en scène). */
  controlsExtra?: ReactNode;
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
  thinkingText,
  funds,
  scan = null,
  scars,
  suspicion,
  motionVotes,
  motionTarget = null,
  onCountryClick,
  mascotVisible = false,
  mascotTarget = null,
  fiche = null,
  onFicheClose,
  dialogues,
  paris,
  renseignement,
  dock,
  overlay,
  brand,
  controlsExtra,
  fallback = {},
}: GlobeTheatreProps) {
  const t = useT();
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
    <div data-tour="scene" aria-label={t("theatre.aria-scene")}>
      {/* --- LE PLATEAU : le globe occupe tout le viewport, cliquable ------------- */}
      <div className="fixed inset-0 z-0 bg-[#04060c]">
        {use3D ? (
          <GlobeStage
            countries={view.countries}
            uByCountry={view.uByCountry}
            utopia={utopia}
            speaking={view.speaking}
            thinking={view.thinking}
            thinkingText={thinkingText}
            misled={view.misled}
            suspended={view.suspended}
            eventTitle={view.eventTitle}
            eventGeo={view.eventGeo}
            pulse={view.pulse}
            frozen={frozen}
            arc={view.arc}
            funds={funds}
            scan={scan}
            scars={scars}
            suspicion={suspicion}
            motionVotes={motionVotes}
            motionTarget={motionTarget}
            view={stageView}
            onViewToggle={toggleView}
            onCountryClick={onCountryClick}
            mascotVisible={mascotVisible}
            mascotTarget={mascotTarget}
            followSpeaker={follow}
            onUserDrag={() => setFollow(false)}
            onUnsupported={() => setWebglOk(false)}
            className="h-full w-full"
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
      </div>

      {/* --- LA COUCHE HUD : fixe, non-interactive ; panneaux enfants interactifs -- */}
      <div className="pointer-events-none fixed inset-0 z-40">
        {/* Marque, haut-gauche. */}
        <div className="pointer-events-auto fixed left-4 top-3 text-xs text-fg-muted">
          {brand ?? (
            <span className="font-semibold uppercase tracking-[0.14em] text-foreground">
              Théâtre des super-intelligences
            </span>
          )}
        </div>

        {/* Bandeau événement, haut-centre (pulsant quand une crise est en cours). */}
        {view.eventTitle && (
          <div className="pointer-events-auto fixed left-1/2 top-3 flex max-w-[min(680px,72vw)] -translate-x-1/2 items-center gap-2.5 border border-edge-strong bg-background/85 px-4 py-2 backdrop-blur thk-cut-sm">
            <span
              aria-hidden
              className="inline-block h-2 w-2 shrink-0 rounded-full bg-[var(--amber)]"
              style={{ boxShadow: "0 0 12px 2px rgba(255,193,77,.8)" }}
            />
            <span className="truncate text-[13px] font-semibold">{view.eventTitle}</span>
          </div>
        )}

        {/* Pop-ups de scène (paris éclair) — hors de la colonne droite. */}
        {overlay && (
          <div className="pointer-events-none fixed inset-0 z-20 md:right-[404px]">{overlay}</div>
        )}

        {/* Fiche pays : tiroir gauche (slide-in). */}
        <div
          className={`pointer-events-auto fixed bottom-20 left-4 top-16 z-30 w-[300px] max-w-[85%] transition-transform duration-300 motion-reduce:transition-none ${
            fiche ? "translate-x-0" : "pointer-events-none -translate-x-[115%]"
          }`}
        >
          {fiche && (
            <div className="thk-panel thk-cut relative h-full overflow-y-auto p-4">
              <button
                type="button"
                onClick={onFicheClose}
                aria-label={t("theatre.fiche-fermer")}
                className="thk-ghost absolute right-2 top-2 px-2 py-0.5"
              >
                ✕
              </button>
              {fiche}
            </div>
          )}
        </div>

        {/* Contrôles caméra + légende U — bas-gauche. */}
        <div className="pointer-events-auto fixed bottom-3 left-4 z-10 flex flex-wrap items-center gap-2">
          <button
            type="button"
            role="switch"
            aria-checked={follow}
            onClick={() => setFollow((v) => !v)}
            className={`thk-switch ${follow ? "on" : ""}`}
          >
            <span className="sw" aria-hidden />
            {t("theatre.suivre")}
          </button>
          {use3D && (
            <button type="button" onClick={toggleView} className="thk-tab on" title="V">
              {stageView === "3d" ? t("theatre.vue-carte") : t("theatre.vue-globe")}
            </button>
          )}
          <span className="flex items-center gap-1.5 border border-edge bg-background/70 px-2 py-1 text-[11px] text-fg-faint backdrop-blur">
            <span
              aria-hidden
              className="inline-block h-1.5 w-8"
              style={{
                background: "linear-gradient(to right, var(--dystopia), var(--warn), var(--utopia))",
              }}
            />
            <span className="font-mono tabular-nums" style={{ color: uTint(utopia) }}>
              {t("theatre.monde")} : {fmt(utopia)}
            </span>
          </span>
          {controlsExtra}
        </div>

        {/* Hint des raccourcis, bas-droite (au-dessus de la colonne). */}
        <div className="pointer-events-none fixed bottom-3 right-[calc(min(400px,42vw)+16px)] hidden border border-edge bg-background/70 px-2.5 py-1.5 text-[10.5px] text-fg-faint backdrop-blur lg:block thk-cut-sm">
          glisser : tourner · molette : zoom · <b>clic délégué : fiche</b> · <b>V</b> : 2D⇄3D ·
          Échap : fermer
        </div>

        {/* Colonne du théâtre : droite, à onglets + dock. */}
        <div className="pointer-events-auto fixed inset-y-3 right-3 z-10 flex w-[min(400px,42vw)] flex-col gap-2">
          <div className="flex gap-1" role="tablist" aria-label={t("theatre.colonne")}>
            {TABS.map((id) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={tab === id}
                onClick={() => setTab(id)}
                className={`thk-tab ${tab === id ? "on" : ""}`}
              >
                {t(`theatre.tab.${id}`)}
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
      </div>
    </div>
  );
}
