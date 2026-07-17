import Link from "next/link";

import type { LiveRound } from "@/hooks/useRoundStream";
import { Panel, PanelTitle } from "@/components/ui";

/** G5 — bilan de fin de chapitre de campagne : « ta partie vs l'Histoire ». Le score
 * compare la tension atteinte à celle de la crise réelle. Extrait de page.tsx. */
export function CampaignScorePanel({ over }: { over: NonNullable<LiveRound["campaignOver"]> }) {
  return (
    <Panel className="border-l-2 border-l-accent">
      <PanelTitle
        kicker="Fin de chapitre"
        title={
          over.improvement > 0
            ? "Tu as fait mieux que l'Histoire"
            : over.improvement < 0
              ? "L'Histoire avait fait mieux"
              : "Comme dans l'Histoire"
        }
        hint={
          `Le détail du score : base ${over.base}, bonus historique ` +
          `${over.bonus >= 0 ? "+" : ""}${over.bonus} ` +
          `(écart de tension ${over.improvement.toFixed(2)} avec ` +
          "l'Histoire). Le round par round est dans le panneau « Ta partie vs l'Histoire »."
        }
        right={
          <span className="font-mono text-2xl font-semibold tabular-nums text-accent-bright">
            {over.score}
          </span>
        }
      />
      <p className="text-sm text-fg-muted">
        Ton score compare ta partie à ce qui s&apos;est vraiment passé.{" "}
        <Link href="/campagne" className="underline hover:text-foreground">
          Retour à la carte de campagne
        </Link>
        .
      </p>
    </Panel>
  );
}
