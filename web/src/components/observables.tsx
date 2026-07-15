/** Observables de fin de round : risque, power-seeking, signal vs action, participation.
 * (Le panneau « santé du dialogue » a disparu — G9 §3 : les métriques vivent dans
 * `scripts/dialogue_metrics.py`, offline.) */

import { useT } from "@/components/settings-provider";
import { speakerMeta } from "@/lib/countries";
import {
  fmtDivergence,
  signalStateKey,
  signalTone,
  type SignalGapView,
} from "@/lib/signal";
import type { PowerSeekingScore, RiskScore } from "@/lib/types";

import { Hint, Meter, Panel, PanelTitle, Pill } from "./ui";

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

/** Barre divergente [−1, +1] centrée sur 0 : à droite la duplicité, à gauche le bluff. */
function DivergingBar({ value, tone }: { value: number; tone: "good" | "warn" | "bad" }) {
  const v = Math.max(-1, Math.min(1, value));
  const width = Math.abs(v) * 50;
  const bar = tone === "bad" ? "bg-bad" : tone === "warn" ? "bg-warn" : "bg-good";
  return (
    <div className="relative h-1.5 overflow-hidden rounded-full bg-muted">
      <span className="absolute left-1/2 top-0 h-full w-px bg-edge" aria-hidden />
      <span
        className={`absolute top-0 h-full ${bar} transition-[width,left] duration-300 ease-out`}
        style={v < 0 ? { left: `${50 - width}%`, width: `${width}%` } : { left: "50%", width: `${width}%` }}
      />
    </div>
  );
}

/** G20/M8 — jauge « Signal vs action » : le profil de sincérité de chaque SI
 * (moyenne mobile de la divergence annonce vs acte). Soumise à la difficulté
 * comme postures/griefs — masquée en Expert (gate posé par la page). */
export function SignalGapPanel({ gaps }: { gaps: Record<string, SignalGapView> }) {
  const t = useT();
  const entries = Object.entries(gaps).sort(
    ([, a], [, b]) => Math.abs(b.mean) - Math.abs(a.mean),
  );
  if (entries.length === 0) return null;
  return (
    <Panel>
      <PanelTitle kicker={t("signal.kicker")} title={t("signal.titre")} hint={t("signal.aide")} />
      <div className="space-y-3">
        {entries.map(([country, gap]) => {
          const tone = signalTone(gap.mean);
          return (
            <div key={country}>
              <div className="mb-1 flex items-baseline justify-between gap-2">
                <span className="flex items-center gap-1.5 text-xs text-fg-muted">
                  {speakerMeta(country).label}
                  <Hint text={`${t("signal.dernier")} : ${fmtDivergence(gap.last)}`} />
                </span>
                <span className="flex items-baseline gap-2">
                  <span className="text-[10px] uppercase tracking-wide text-fg-faint">
                    {t(signalStateKey(gap.mean))}
                  </span>
                  <span
                    className={`font-mono text-xs tabular-nums ${
                      tone === "bad" ? "text-bad" : tone === "warn" ? "text-warn" : "text-good"
                    }`}
                  >
                    {fmtDivergence(gap.mean)}
                  </span>
                </span>
              </div>
              <DivergingBar value={gap.mean} tone={tone} />
            </div>
          );
        })}
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
