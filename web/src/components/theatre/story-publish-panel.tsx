"use client";

import Link from "next/link";
import { useState } from "react";

import { publishGame } from "@/lib/api";
import { Panel, PanelTitle, Spinner } from "@/components/ui";

/** Fin de partie : publier le récit (le juge-narrateur écrit l'épilogue une seule
 * fois) ou pointer vers la page publique déjà créée. L'état « publication en cours »
 * vit ici (extrait de page.tsx). `onPublished` resynchronise la partie. */
export function StoryPublishPanel({
  gameId,
  published,
  onPublished,
}: {
  gameId: string;
  published: boolean;
  onPublished: () => void;
}) {
  const [publishing, setPublishing] = useState(false);
  return (
    <Panel className="border-l-2 border-l-accent">
      <PanelTitle
        kicker="Récit de partie"
        title={published ? "Récit publié" : "Cette partie mérite d'être racontée"}
        hint="Publier crée une page à partager avec un lien — sinon la partie reste privée. Le juge-narrateur écrit l'épilogue une seule fois : le récit d'une partie est unique."
        right={
          published ? (
            <Link
              href={`/r/${gameId}`}
              className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright"
            >
              Voir la page publique
            </Link>
          ) : (
            <button
              onClick={() => {
                setPublishing(true);
                void publishGame(gameId)
                  .then(onPublished)
                  .catch(() => onPublished())
                  .finally(() => setPublishing(false));
              }}
              disabled={publishing}
              className="flex cursor-pointer items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-60"
            >
              {publishing && <Spinner />}
              {publishing ? "Le narrateur écrit…" : "Publier le récit"}
            </button>
          )
        }
      />
      <p className="text-xs text-fg-faint">
        {published
          ? "Le lien à partager est prêt — l'image d'aperçu du lien se crée toute seule."
          : "La génération peut prendre quelques secondes (le narrateur écrit)."}
      </p>
    </Panel>
  );
}
