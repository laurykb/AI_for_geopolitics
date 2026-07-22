"use client";

/** HUD utilitaire mince (spec coquille §3, Inc 1 = socle).
 *
 * Inc 1 : un simple fil d'Ariane de la phase courante, posé sur `/` (où
 * `SiteHeader` est absent — pas de collision). Le HUD complet (pastille joueur,
 * menu réglages/profil/déconnexion, langue, « retour au hall ») remplacera
 * `SiteHeader` à l'Inc 5. */

import { usePathname } from "next/navigation";

import { useStageDirector } from "@/components/shell/stage-provider";
import type { Phase } from "@/lib/stage-director";

const PHASE_LABEL: Record<Phase, string> = {
  connexion: "Connexion",
  hall: "Le hall",
  config: "Composer le sommet",
  theatre: "En partie",
  fin: "Cérémonie",
};

export function Hud() {
  const pathname = usePathname();
  const { phase } = useStageDirector();

  // Inc 1 : uniquement sur la coquille `/` (SiteHeader gère le reste).
  if (pathname !== "/") return null;

  return (
    <div className="pointer-events-none fixed left-4 top-4 z-40">
      <span className="thk-block-label bg-background/70 px-2 py-1 backdrop-blur">
        {PHASE_LABEL[phase]}
      </span>
    </div>
  );
}
