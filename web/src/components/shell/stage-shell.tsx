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
import { useCallback } from "react";

import { useSettings } from "@/components/settings-provider";
import { Hud } from "@/components/shell/hud";
import { useStageDirector } from "@/components/shell/stage-provider";

const GlobeStage = dynamic(
  () => import("@/components/globe/globe-stage").then((m) => m.GlobeStage),
  { ssr: false },
);

export function StageShell() {
  const pathname = usePathname();
  const { stage, handlers } = useStageDirector();
  const { settings, setStageView } = useSettings();

  const onCountryClick = useCallback(
    (slug: string) => handlers.current.onCountryClick?.(slug),
    [handlers],
  );
  const onUserDrag = useCallback(() => handlers.current.onUserDrag?.(), [handlers]);
  const onUnsupported = useCallback(() => handlers.current.onUnsupported?.(), [handlers]);
  const onViewToggle = useCallback(() => {
    handlers.current.onViewToggle?.();
    setStageView(settings.stageView === "3d" ? "2d" : "3d");
  }, [handlers, setStageView, settings.stageView]);

  // Le théâtre garde son globe jusqu'à l'Inc 4 ; le partage public reste nu.
  const hidden = pathname.startsWith("/r/") || pathname.startsWith("/games/");
  if (hidden) return null;

  const { countries = [], uByCountry = {}, utopia = 0.5, ...rest } = stage;

  return (
    <>
      {/* Fond plein-cadre, derrière le contenu ; non interactif en Inc 1. */}
      <div className="pointer-events-none fixed inset-0 -z-10" aria-hidden>
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
