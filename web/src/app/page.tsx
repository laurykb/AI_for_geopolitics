"use client";

/** `/` — le point d'entrée unique de la coquille (spec coquille §2-§4).
 *
 * Non authentifié → l'espace connexion posé sur le globe persistant (`StageShell`).
 * Authentifié → le hall (transitoire Inc 2 : redirection vers `/accueil` ; l'overlay
 * hall vivra ici même dès l'Inc 3, sans navigation). */

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth-provider";
import { ConnexionOverlay } from "@/components/shell/connexion-overlay";
import { useStageDirector } from "@/components/shell/stage-provider";
import { Spinner } from "@/components/ui";

export default function ShellEntry() {
  const router = useRouter();
  const { player, loading } = useAuth();
  const { goPhase } = useStageDirector();

  // Le globe affiche le fond de connexion tant qu'on est sur cette entrée.
  useEffect(() => {
    goPhase("connexion");
  }, [goPhase]);

  // Session déjà ouverte → le hall (transitoire : /accueil, remplacé en Inc 3).
  useEffect(() => {
    if (!loading && player) router.replace("/accueil");
  }, [loading, player, router]);

  if (loading || player) {
    return (
      <p className="flex min-h-[50vh] items-center justify-center gap-2 text-sm text-fg-muted">
        <Spinner /> {loading ? "Chargement…" : "Ouverture du hall…"}
      </p>
    );
  }

  return <ConnexionOverlay />;
}
