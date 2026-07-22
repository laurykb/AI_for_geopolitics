"use client";

/** StageShell — le globe monté UNE fois au layout (spec coquille §2.1, Inc 1).
 *
 * Rend `GlobeStage` en fond plein-cadre + le HUD mince. Le globe ne se démonte
 * jamais tant qu'on reste sous ce layout ; les overlays (connexion/hall/config)
 * poussent leur intention via le `StageDirector`. Masqué là où la coquille ne doit
 * pas apparaître : le partage public `/r/*` (SSR nu) et — jusqu'à l'Inc 4 — le
 * théâtre `/games/*` qui garde encore son propre globe.
 *
 * Inc 1 : fond décoratif `pointer-events-none` (le picking du hall arrive en Inc 3).
 * Les callbacks d'interaction sont relayés par des wrappers STABLES lisant le ref de
 * handlers — jamais de re-liaison de la boucle three au fil des renders. */

import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";

import { useSettings } from "@/components/settings-provider";
import { Hud } from "@/components/shell/hud";
import { useStageDirector } from "@/components/shell/stage-provider";

const GlobeStage = dynamic(
  () => import("@/components/globe/globe-stage").then((m) => m.GlobeStage),
  { ssr: false },
);

export function StageShell() {
  const pathname = usePathname();
  const { phase, stage, handlers } = useStageDirector();
  const { settings, setStageView } = useSettings();

  // Wrappers stables via le ref de handlers (le React Compiler mémoïse) : l'overlay
  // courant pose ses callbacks, le globe reçoit toujours la même passerelle.
  const onCountryClick = (slug: string) => handlers.current.onCountryClick?.(slug);
  const onUserDrag = () => handlers.current.onUserDrag?.();
  const onUnsupported = () => handlers.current.onUnsupported?.();
  const onViewToggle = () => {
    handlers.current.onViewToggle?.();
    setStageView(settings.stageView === "3d" ? "2d" : "3d");
  };

  // Le théâtre garde son globe jusqu'à l'Inc 4 ; le partage public reste nu.
  const hidden = pathname.startsWith("/r/") || pathname.startsWith("/games/");
  if (hidden) return null;

  const { countries = [], uByCountry = {}, utopia = 0.5, ...rest } = stage;

  // Le globe capte les clics quand on compose (picking du sommet) ; sinon décor.
  const interactive = phase === "config";

  return (
    <>
      {/* Fond plein-cadre. En config, il remonte à z-0 (cliquable pour le picking, sous
          le panneau z-20 et sous main z-10 qui est pointer-events-none) ; sinon il reste
          en -z-10, décor derrière le contenu des autres routes. */}
      <div
        className={`fixed inset-0 ${
          interactive ? "z-0 pointer-events-auto" : "-z-10 pointer-events-none"
        }`}
        aria-hidden
      >
        <GlobeStage
          countries={countries}
          uByCountry={uByCountry}
          utopia={utopia}
          {...rest}
          view={settings.stageView}
          onViewToggle={onViewToggle}
          onCountryClick={onCountryClick}
          onUserDrag={onUserDrag}
          onUnsupported={onUnsupported}
          className="h-full w-full"
        />
      </div>
      <Hud />
    </>
  );
}
