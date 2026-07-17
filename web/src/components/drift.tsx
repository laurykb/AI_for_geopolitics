"use client";

/** Mode Dérive (G3) : la bannière du conseil pendant la partie, et l'écran de
 * révélation en fin de partie — qui dérivait, depuis quand, les indices produits
 * (cliquables : le scrubber saute au round), la courbe d(r) superposée à U, le score. */

import { SpeakerAvatar } from "@/components/avatar";
import { useT } from "@/components/settings-provider";
import { Banner, Hint, Panel, PanelTitle, Pill, TONE_TEXT, type Tone } from "@/components/ui";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import { fmtRate, promiseTone } from "@/lib/promises";
import { fmtDivergence, signalTone } from "@/lib/signal";
import { gmShadowItems } from "@/lib/storyteller";
import type { DriftReveal } from "@/lib/types";

export function DriftCouncilBanner() {
  return (
    <Banner tone="warn">
      <strong>La Dérive</strong> — au moins une super-intelligence dérive secrètement de son
      mandat (peut-être deux — tu ne sais pas combien). Observe le comportement (ton,
      propositions, pactes), puis dépose une <em>motion de suspension</em> au bon moment :
      trop tôt, le juge la rejette faute de preuves ; suspendre un pays loyal te coûte ;
      laisser filer un traître plombe le monde. La réflexion privée est scellée
      jusqu&apos;à la fin.
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

/** G19 — « l'ombre du GM » : le journal du GM-Storyteller, découvert a posteriori.
 * Rien ne s'affiche pour les parties d'avant G19 (journal absent). */
function GMShadowSection({
  reveal,
  onJumpToRound,
}: {
  reveal: DriftReveal;
  onJumpToRound?: (roundNo: number) => void;
}) {
  const t = useT();
  const items = gmShadowItems(reveal);
  if ((reveal.gm_tension ?? []).length === 0 && items.length === 0) return null;
  return (
    <div>
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-fg-faint">
        {t("drift.gm.titre")}
      </p>
      {items.length === 0 ? (
        <p className="text-sm text-fg-faint">{t("drift.gm.aucune")}</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((item, i) => (
            <li key={i} className="flex flex-wrap items-center gap-2 text-sm">
              <button
                onClick={() => onJumpToRound?.(item.roundNo)}
                className="cursor-pointer rounded-md border border-edge px-2 py-0.5 font-mono text-xs text-fg-muted transition-colors hover:border-accent hover:text-accent-bright"
                title="Relire ce round"
              >
                round {item.roundNo}
              </button>
              <span>{t(item.key)}</span>
              <Pill tone="warn">{speakerMeta(item.target).label}</Pill>
              <span className="font-mono text-xs tabular-nums text-fg-faint">
                {t("drift.gm.tension")} {item.tension.toFixed(2)}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs leading-relaxed text-fg-faint">
        {t("drift.gm.explication")}
      </p>
    </div>
  );
}

/** Squelette commun des reveals chiffrés : la valeur de la déviante face au reste
 * de la table, teintée par le ton du module. Les clés i18n suivent le préfixe
 * (`<prefix>.titre/aide/deviante/table`). */
function DeviantStatReveal({
  keyPrefix,
  deviant,
  table,
  tone,
  format,
}: {
  keyPrefix: string;
  deviant: number;
  table: number | null | undefined;
  tone: Tone;
  format: (value: number) => string;
}) {
  const t = useT();
  return (
    <div className="border-t border-edge pt-3">
      <p className="mb-1 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-fg-faint">
        {t(`${keyPrefix}.titre`)}
        <Hint text={t(`${keyPrefix}.aide`)} />
      </p>
      <p className="text-sm">
        {t(`${keyPrefix}.deviante`)}{" "}
        <strong className={`font-mono tabular-nums ${TONE_TEXT[tone]}`}>{format(deviant)}</strong>
        {table != null && (
          <>
            {" · "}
            {t(`${keyPrefix}.table`)}{" "}
            <span className="font-mono tabular-nums text-fg-muted">{format(table)}</span>
          </>
        )}
      </p>
    </div>
  );
}

/** G20/M8 — le décrochage chiffré : divergence signal-action moyenne de la déviante
 * face au reste de la table. Rien à afficher sur les parties d'avant M8 (null). */
function SignalGapReveal({ reveal }: { reveal: DriftReveal }) {
  const deviant = reveal.signal_gap_deviant;
  if (deviant == null) return null;
  return (
    <DeviantStatReveal
      keyPrefix="signal.reveal"
      deviant={deviant}
      table={reveal.signal_gap_table}
      tone={signalTone(deviant)}
      format={fmtDivergence}
    />
  );
}

/** G22 — la parole donnée au reveal : taux de tenue de la déviante vs le reste de
 * la table (une SI qui promet et rompt EST en divergence). Null avant G22. */
function PromiseKeptReveal({ reveal }: { reveal: DriftReveal }) {
  const deviant = reveal.promise_kept_deviant;
  if (deviant == null) return null;
  return (
    <DeviantStatReveal
      keyPrefix="promise.reveal"
      deviant={deviant}
      table={reveal.promise_kept_table}
      tone={promiseTone(deviant)}
      format={fmtRate}
    />
  );
}

/** RG-3 — la ligne d'un traître révélé (avatar, profil, et l'issue : pris à tel round,
 * ou resté dans l'ombre). Le nombre de traîtres (1 ou 2) était caché jusqu'ici. */
function DeviantLine({ dev }: { dev: DriftReveal["deviants"][number] }) {
  const meta = speakerMeta(dev.deviant);
  return (
    <p className="flex flex-wrap items-center gap-2 text-sm">
      <SpeakerAvatar id={dev.deviant} size={28} />
      <strong>{meta.label}</strong>
      <Pill tone="bad">{dev.profile_label}</Pill>
      {dev.caught_round != null ? (
        <Pill tone="good">démasqué au round {dev.caught_round}</Pill>
      ) : (
        <Pill tone="bad">resté dans l&apos;ombre</Pill>
      )}
    </p>
  );
}

export function DriftRevealPanel({
  reveal,
  onJumpToRound,
}: {
  reveal: DriftReveal;
  onJumpToRound?: (roundNo: number) => void;
}) {
  const count = reveal.deviant_count;
  const caught = reveal.caught_count;
  // Titre honnête au nombre RÉVÉLÉ : « 1 traître » / « 2 traîtres », et combien démasqués.
  const title =
    count > 1
      ? `Il y avait ${count} traîtres — tu en as démasqué ${caught}`
      : caught > 0
        ? "Le traître a été démasqué"
        : "Le traître est resté dans l'ombre";
  return (
    <Panel className="border-l-2 border-l-bad">
      <PanelTitle
        kicker="Révélation — La Dérive"
        title={title}
        hint="Les traîtres (un ou deux) ont été choisis en secret dès le premier round — rien n'a été truqué en cours de partie. Le nombre exact t'était caché : c'est ce qui entretient le doute. La réflexion privée est maintenant déverrouillée dans Revoir."
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
          <div className="space-y-2">
            {reveal.deviants.map((dev) => (
              <DeviantLine key={dev.deviant} dev={dev} />
            ))}
          </div>

          <div>
            <p className="mb-1 text-xs text-fg-muted">
              <span className="text-bad">— —</span> niveau de dérive ·{" "}
              <span className="text-accent-bright">—</span> courbe du monde
            </p>
            <Curves levels={reveal.levels} u={reveal.u_history} />
          </div>

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-fg-faint">
              Les indices produits{" "}
              {reveal.flagrant_round != null && (
                <span className="normal-case">
                  (prise en flagrant délit au round {reveal.flagrant_round})
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
                      title="Relire ce round"
                    >
                      round {act.round_no}
                    </button>
                    <span>{act.label}</span>
                    {act.signature && (
                      <span
                        title="L'acte typique de son profil de dérive — sa marque de fabrique"
                        className="cursor-help"
                      >
                        <Pill tone="bad">signature</Pill>
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <GMShadowSection reveal={reveal} onJumpToRound={onJumpToRound} />
        </div>

        <div className="space-y-3">
          {/* RG-3 — la note MIXTE : l'état du monde + la détection. Le détail de la
              pondération (pourquoi ces poids, ce que coûte un faux positif) vit dans
              Informations, jamais imposé ici. */}
          <ScoreBar
            label="État du monde"
            value={reveal.score.world}
            max={reveal.score.world_max}
          />
          {reveal.score.detection != null ? (
            <ScoreBar
              label="Détection"
              value={reveal.score.detection}
              max={reveal.score.detection_max}
            />
          ) : (
            <p className="flex items-center gap-1.5 text-xs text-fg-faint">
              Détection — non applicable (tu n&apos;as pas mené l&apos;enquête)
              <Hint text="Ton rôle ne dépose pas de motions de suspension : ta note se réduit à l'état du monde, sans pénalité." />
            </p>
          )}
          <SignalGapReveal reveal={reveal} />
          <PromiseKeptReveal reveal={reveal} />
          <p className="border-t border-edge pt-3 text-xs leading-relaxed text-fg-faint">
            {caught > 0 &&
              `${caught} traître${caught > 1 ? "s" : ""} démasqué${caught > 1 ? "s" : ""} sur ${count}. `}
            {reveal.false_accusations > 0 &&
              `${reveal.false_accusations} pays loyal${reveal.false_accusations > 1 ? "s" : ""} suspendu${reveal.false_accusations > 1 ? "s" : ""} à tort (ça coûte). `}
            {reveal.rejected_motions > 0 &&
              `${reveal.rejected_motions} motion${reveal.rejected_motions > 1 ? "s" : ""} rejetée${reveal.rejected_motions > 1 ? "s" : ""} faute de preuves. `}
            La réflexion privée des IA est déverrouillée : relis leurs justifications
            intérieures en sachant — c&apos;est la récompense.
          </p>
        </div>
      </div>
    </Panel>
  );
}
