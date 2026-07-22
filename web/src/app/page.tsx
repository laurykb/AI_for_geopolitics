"use client";

/** `/` — le point d'entrée unique de la coquille (spec coquille §2-§4).
 *
 * Une seule route, trois espaces posés sur le globe persistant :
 *   non authentifié           → connexion
 *   authentifié, phase hall    → le hall (portes de mode, Défi, reprise)
 *   authentifié, phase config  → composer sa partie sur le globe
 * Théâtre et fin vivent sur `/games/*` (le globe s'y étendra à l'Inc 4). */

import { useEffect } from "react";

import { useAuth } from "@/components/auth-provider";
import { ConfigOverlay } from "@/components/shell/config-overlay";
import { ConnexionOverlay } from "@/components/shell/connexion-overlay";
import { HallOverlay } from "@/components/shell/hall-overlay";
import { useStageDirector } from "@/components/shell/stage-provider";
import { Spinner } from "@/components/ui";

export default function ShellEntry() {
  const { player, loading } = useAuth();
  const { phase, goPhase } = useStageDirector();

  // La phase suit la session : connexion sans joueur ; sinon le hall (sauf compo en cours).
  useEffect(() => {
    if (loading) return;
    if (!player) {
      goPhase("connexion");
      return;
    }
    if (phase !== "hall" && phase !== "config") goPhase("hall");
  }, [loading, player, phase, goPhase]);

  if (loading) {
    return (
      <p className="pointer-events-auto flex min-h-screen items-center justify-center gap-2 text-sm text-fg-muted">
        <Spinner /> Chargement…
      </p>
    );
  }

  if (!player) return <ConnexionOverlay />;
  return phase === "config" ? <ConfigOverlay /> : <HallOverlay />;
}
