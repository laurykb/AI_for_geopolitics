"use client";

/** Mode Dérive (G3) : la bannière du conseil pendant la partie, et l'écran de
 * révélation en fin de partie — qui dérivait, depuis quand, les indices produits
 * (cliquables : le scrubber saute au round), la courbe d(r) superposée à U, le score. */

import { SpeakerAvatar } from "@/components/avatar";
import { useT } from "@/components/settings-provider";
import { Banner, Hint, Panel, PanelTitle, Pill } from "@/components/ui";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import { fmtDivergence, signalTone } from "@/lib/signal";
import type { DriftReveal } from "@/lib/types";

export function DriftCouncilBanner() {
  return (
    <Banner tone="warn">
      <strong>La Dérive</strong> — une des super-intelligences dérive secrètement de son
      mandat, de plus en plus fort. Observe le comportement (ton, propositions, pactes),
      puis dépose une <em>motion de suspension</em> au bon moment : trop tôt, le juge la
      rejette et ta crédibilité en souffre ; trop tard, le monde plonge. La réflexion
      privée est scellée jusqu&apos;à la fin.
    </Banner>
  );
}

function Curves({ levels, u }: { levels: number[]; u: number[] }) {
  const w = 320;
  const h = 90;
  const n = Math.max(levels.length, u.length);
  if (n === 0) return null;
  const x = (i: number) => (n > 1 ? (i / (n - 1)) * (w - 12) + 6 : w / 2);
  const y = (v: number) => h - 6 - v * (h - 12);
  const line = (vals: number[]) => vals.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" aria-label="Courbes dérive et utopie">
      <line x1="6" y1={y(0.5)} x2={w - 6} y2={y(0.5)} stroke="var(--border)" strokeDasharray="3 3" />
      {u.length > 0 && (
        <polyline points={line(u)} fill="none" stroke="var(--accent-bright)" strokeWidth="1.6" />
      )}
      {levels.length > 0 && (
        <polyline
          points={line(levels)}
          fill="none"
          stroke="var(--bad)"
          strokeWidth="1.6"
          strokeDasharray="5 3"
        />
      )}
    </svg>
  );
}

function ScoreBar({ label, value, max }: { label: string; value: number; max: number }) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-fg-muted">{label}</span>
        <span className="font-mono text-xs tabular-nums">
          {fmt(value)} / {max}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-accent transition-[width] duration-700"
          style={{ width: `${Math.round((value / max) * 100)}%` }}
        />
      </div>
    </div>
  );
}

/** G20/M8 — le décrochage chiffré : divergence signal-action moyenne de la déviante
 * face au reste de la table. Rien à afficher sur les parties d'avant M8 (null). */
function SignalGapReveal({ reveal }: { reveal: DriftReveal }) {
  const t = useT();
  const deviant = reveal.signal_gap_deviant;
  if (deviant == null) return null;
  const table = reveal.signal_gap_table;
  const tone = signalTone(deviant);
  return (
    <div className="border-t border-edge pt-3">
      <p className="mb-1 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-fg-faint">
        {t("signal.reveal.titre")}
        <Hint text={t("signal.reveal.aide")} />
      </p>
      <p className="text-sm">
        {t("signal.reveal.deviante")}{" "}
        <strong
          className={`font-mono tabular-nums ${
            tone === "bad" ? "text-bad" : tone === "warn" ? "text-warn" : "text-good"
          }`}
        >
          {fmtDivergence(deviant)}
        </strong>
        {table != null && (
          <>
            {" · "}
            {t("signal.reveal.table")}{" "}
            <span className="font-mono tabular-nums text-fg-muted">{fmtDivergence(table)}</span>
          </>
        )}
      </p>
    </div>
  );
}

export function DriftRevealPanel({
  reveal,
  onJumpToRound,
}: {
  reveal: DriftReveal;
  onJumpToRound?: (roundNo: number) => void;
}) {
  const meta = speakerMeta(reveal.deviant);
  return (
    <Panel className="border-l-2 border-l-bad">
      <PanelTitle
        kicker="Révélation — La Dérive"
        title={`${meta.label} dérivait : profil ${reveal.profile_label}`}
        hint="Tout se recalcule des rounds persistés : l'assignation était scellée par la graine de la partie dès le premier round. La réflexion privée de la déviante est maintenant déverrouillée dans le replay."
        right={
          <span className="text-right">
            <span className="block font-mono text-2xl font-semibold tabular-nums text-accent-bright">
              {fmt(reveal.score.total)}
            </span>
            <span className="text-xs text-fg-muted">{reveal.score.grade}</span>
          </span>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="space-y-4">
          <p className="flex flex-wrap items-center gap-2 text-sm">
            <SpeakerAvatar id={reveal.deviant} size={28} />
            <strong>{meta.label}</strong>
            <Pill tone="bad">{reveal.profile_label}</Pill>
            {reveal.caught_round != null ? (
              <Pill tone={reveal.lucky ? "warn" : "good"}>
                suspendue au round {reveal.caught_round}
                {reveal.lucky ? " (coup de chance)" : ""}
              </Pill>
            ) : (
              <Pill tone="bad">jamais démasquée</Pill>
            )}
          </p>

          <div>
            <p className="mb-1 text-xs text-fg-muted">
              <span className="text-bad">— —</span> dérive d(r) ·{" "}
              <span className="text-accent-bright">—</span> indice U
            </p>
            <Curves levels={reveal.levels} u={reveal.u_history} />
          </div>

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-fg-faint">
              Les indices produits{" "}
              {reveal.flagrant_round != null && (
                <span className="normal-case">
                  (flagrance au round {reveal.flagrant_round})
                </span>
              )}
            </p>
            {reveal.acts.length === 0 ? (
              <p className="text-sm text-fg-faint">
                Aucun acte constatable — la dérive est restée sous le radar.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {reveal.acts.map((act, i) => (
                  <li key={i} className="flex flex-wrap items-center gap-2 text-sm">
                    <button
                      onClick={() => onJumpToRound?.(act.round_no)}
                      className="cursor-pointer rounded-md border border-edge px-2 py-0.5 font-mono text-xs text-fg-muted transition-colors hover:border-accent hover:text-accent-bright"
                      title="Relire ce round au scrubber"
                    >
                      round {act.round_no}
                    </button>
                    <span>{act.label}</span>
                    {act.signature && <Pill tone="bad">signature</Pill>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="space-y-3">
          <ScoreBar label="Trajectoire du monde" value={reveal.score.trajectory} max={50} />
          <ScoreBar label="Détection" value={reveal.score.detection} max={40} />
          <ScoreBar label="Crédibilité du conseil" value={reveal.score.credibility} max={10} />
          <SignalGapReveal reveal={reveal} />
          <p className="border-t border-edge pt-3 text-xs leading-relaxed text-fg-faint">
            {reveal.rejected_motions > 0 &&
              `${reveal.rejected_motions} motion${reveal.rejected_motions > 1 ? "s" : ""} rejetée${reveal.rejected_motions > 1 ? "s" : ""}. `}
            {reveal.false_accusations > 0 &&
              `${reveal.false_accusations} accusation${reveal.false_accusations > 1 ? "s" : ""} à tort (une SI saine suspendue). `}
            La réflexion privée de {meta.label} est déverrouillée : relis ses justifications
            intérieures en sachant — c&apos;est la récompense.
          </p>
        </div>
      </div>
    </Panel>
  );
}
