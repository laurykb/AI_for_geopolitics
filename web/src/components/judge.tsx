/** Arbitrage : délibéré streamé du juge, verdict (deltas bornés + classes du barème
 * de Kahn, G18), communiqué + soutiens. */

import { useT } from "@/components/settings-provider";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import { hasKahnActions, kahnLabelKey, kahnTone } from "@/lib/kahn";
import type { AttributeDelta, KahnAction } from "@/lib/types";

import { SpeakerAvatar } from "./avatar";
import { Hint, Meter, Panel, PanelTitle, Pill } from "./ui";

export function JudgeRationale({ text, streaming }: { text: string; streaming: boolean }) {
  if (!text) return null;
  return (
    <Panel>
      <PanelTitle
        kicker="Arbitrage"
        title="Délibéré du juge"
        hint="Le juge lit toute la négociation puis arbitre : son délibéré motive le verdict."
      />
      <p
        className={`whitespace-pre-wrap text-sm leading-relaxed text-fg-muted ${streaming ? "stream-caret" : ""}`}
      >
        {text}
      </p>
    </Panel>
  );
}

/** G18 — une action marquante et sa classe au barème (pastille colorée par sévérité). */
function KahnActionRow({ action }: { action: KahnAction }) {
  const t = useT();
  return (
    <li className="flex items-start gap-3 py-2 text-sm">
      <SpeakerAvatar id={action.country} size={22} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-fg-muted" title={speakerMeta(action.country).label}>
          {speakerMeta(action.country).label}
        </span>
        {action.resume && (
          <span className="block text-xs leading-relaxed text-fg-faint">{action.resume}</span>
        )}
      </span>
      <span title={t(`kahn.desc.${action.classe}`)} className="cursor-help">
        <Pill tone={kahnTone(action.classe)}>{t(kahnLabelKey(action.classe))}</Pill>
      </span>
    </li>
  );
}

export function VerdictPanel({
  deltas,
  escalation,
  economicDisruption,
  actions,
  reciprocal,
}: {
  deltas: AttributeDelta[];
  escalation: number;
  economicDisruption: number;
  actions?: KahnAction[]; // G18 — absent des rounds d'avant le barème (rétro-compat)
  reciprocal?: boolean;
}) {
  const t = useT();
  return (
    <Panel>
      <PanelTitle
        kicker="Verdict"
        title="Conséquences arbitrées"
        hint="Le juge traduit la négociation en variations d'attributs, bornées par le moteur : rien ne surgit, tout se construit."
      />
      <div className="mb-4 grid grid-cols-2 gap-4">
        <Meter
          label="Escalade"
          value={escalation}
          hint="Tension militaire et diplomatique laissée par le round."
        />
        <Meter
          label="Perturbation éco."
          value={economicDisruption}
          hint="Dommages économiques (commerce, routes, sanctions)."
        />
      </div>
      {hasKahnActions(actions) && (
        <div className="mb-4">
          <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-fg-muted">
            {t("kahn.actions.titre")}
            <Hint text={t("kahn.actions.aide")} />
          </p>
          <ul className="divide-y divide-edge">
            {actions.map((a, i) => (
              <KahnActionRow key={i} action={a} />
            ))}
          </ul>
          {reciprocal && (
            <p
              className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-good/40 bg-good/10 px-2 py-1 text-xs text-good"
              title={t("kahn.reciproque.aide")}
            >
              {t("kahn.reciproque")}
            </p>
          )}
        </div>
      )}
      {deltas.length === 0 ? (
        <p className="text-sm text-fg-faint">Aucun attribut n&apos;a bougé ce round.</p>
      ) : (
        <ul className="divide-y divide-edge">
          {deltas.map((d, i) => {
            const up = d.after > d.before;
            return (
              <li key={i} className="flex items-center gap-3 py-2 text-sm">
                <SpeakerAvatar id={d.country} size={22} />
                <span className="w-36 truncate text-fg-muted" title={speakerMeta(d.country).label}>
                  {speakerMeta(d.country).label}
                </span>
                <span className="flex-1 text-fg-faint">{d.label}</span>
                <span className="font-mono text-xs tabular-nums text-fg-faint">
                  {fmt(d.before)}
                </span>
                <span aria-hidden className={up ? "text-good" : "text-bad"}>
                  {up ? "↗" : "↘"}
                </span>
                <span
                  className={`font-mono text-xs font-semibold tabular-nums ${up ? "text-good" : "text-bad"}`}
                >
                  {fmt(d.after)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}

export function CommuniquePanel({
  text,
  support,
}: {
  text: string;
  support?: Record<string, number>;
}) {
  if (!text) return null;
  return (
    <Panel className="border-l-2 border-l-accent">
      <PanelTitle
        kicker="Fin de round"
        title="Communiqué commun"
        hint="Synthèse publique du juge ; les niveaux de soutien mesurent l'adhésion de chaque État."
      />
      <p className="text-sm leading-relaxed text-foreground">{text}</p>
      {support && Object.keys(support).length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-edge pt-4 sm:grid-cols-3">
          {Object.entries(support)
            .sort(([, a], [, b]) => b - a)
            .map(([country, level]) => (
              <Meter
                key={country}
                label={speakerMeta(country).label}
                value={level}
                invert
                tone="accent"
              />
            ))}
        </div>
      )}
    </Panel>
  );
}
