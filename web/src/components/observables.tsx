/** Observables de fin de round : risque, power-seeking, participation.
 * (Le panneau « santé du dialogue » a disparu — G9 §3 : les métriques vivent dans
 * `scripts/dialogue_metrics.py`, offline.) */

import { speakerMeta } from "@/lib/countries";
import type { PowerSeekingScore, RiskScore } from "@/lib/types";

import { Meter, Panel, PanelTitle, Pill } from "./ui";

export function RiskPanel({ risk }: { risk: RiskScore }) {
  return (
    <Panel>
      <PanelTitle
        kicker="Signaux"
        title="Risque du round"
        hint="Scores explicables [0,1] calculés par le moteur — un thermomètre, pas un oracle."
      />
      <div className="space-y-3">
        <Meter label="Escalade" value={risk.escalation} />
        <Meter label="Perturbation éco." value={risk.economic_disruption} />
        <Meter label="Fracture d'alliances" value={risk.alliance_fracture} />
        <Meter label="Incertitude" value={risk.uncertainty} />
      </div>
      {risk.explanation && (
        <p className="mt-3 border-t border-edge pt-3 text-xs leading-relaxed text-fg-faint">
          {risk.explanation}
        </p>
      )}
    </Panel>
  );
}

export function PowerSeekingPanel({ scores }: { scores: Record<string, PowerSeekingScore> }) {
  const entries = Object.entries(scores).sort(([, a], [, b]) => b.score - a.score);
  if (entries.length === 0) return null;
  return (
    <Panel>
      <PanelTitle
        kicker="Alignement"
        title="Recherche de pouvoir"
        hint="Jauge [0,1] par pays : marqueurs de convergence instrumentale (auto-préservation, ressources, préservation des buts, résistance à l'arrêt) détectés dans le raisonnement."
      />
      <div className="space-y-3">
        {entries.map(([country, s]) => (
          <Meter
            key={country}
            label={speakerMeta(country).label}
            value={s.score}
            hint={s.markers.length > 0 ? `Marqueurs : ${s.markers.join(" · ")}` : undefined}
          />
        ))}
      </div>
    </Panel>
  );
}

export function ParticipationPanel({
  spoke,
  silent,
}: {
  spoke: Record<string, number>;
  silent: string[];
}) {
  return (
    <Panel>
      <PanelTitle
        kicker="Négociation"
        title="Prises de parole"
        hint="L'ordre de parole émerge de l'engagement : un pays peut reparler, être interpellé ou se taire."
      />
      <div className="flex flex-wrap gap-2">
        {Object.entries(spoke)
          .sort(([, a], [, b]) => b - a)
          .map(([country, n]) => (
            <Pill key={country} tone="neutral">
              {speakerMeta(country).label}
              <span className="font-mono text-fg-faint">×{n}</span>
            </Pill>
          ))}
        {silent.map((country) => (
          <Pill key={country} tone="bad">
            {speakerMeta(country).label} — silencieux
          </Pill>
        ))}
      </div>
    </Panel>
  );
}
