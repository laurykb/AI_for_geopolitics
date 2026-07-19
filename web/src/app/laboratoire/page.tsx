"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ResearchLab } from "@/components/research-lab";
import { Banner, Eyebrow, Spinner } from "@/components/ui";
import { getLab, humanizeError } from "@/lib/api";
import type { CampaignLabView } from "@/lib/types";

/** Troisième mode autonome : même socle de simulation, mais protocole, répétitions et
 * résultats remplacent la progression historique de la Campagne. */
export default function LaboratoirePage() {
  const [lab, setLab] = useState<CampaignLabView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLab()
      .then(setLab)
      .catch((err) => setError(humanizeError(err)));
  }, []);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-3xl">
          <Eyebrow>Troisième mode · recherche reproductible</Eyebrow>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            Laboratoire d&apos;expérience
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-fg-muted">
            Observe une crise comme dans le jeu classique, change une seule variable,
            répète l&apos;essai avec plusieurs modèles puis compare ce qui change réellement.
            Chaque résultat reste une mesure du dispositif testé, jamais une prédiction du monde.
          </p>
        </div>
        <nav className="flex flex-wrap gap-2 text-xs">
          <Link
            href="/lobby"
            className="rounded-md border border-edge px-3 py-2 text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
          >
            ← Les trois modes
          </Link>
          <Link
            href="/campagne"
            className="rounded-md border border-edge px-3 py-2 text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
          >
            Voir la Campagne
          </Link>
        </nav>
      </header>

      {error && <Banner tone="bad">{error}</Banner>}
      {!error && !lab && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          <Spinner /> Préparation du laboratoire…
        </p>
      )}
      {lab && <ResearchLab lab={lab} />}
    </div>
  );
}
