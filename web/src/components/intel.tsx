"use client";

/** Le Dossier (G4) : budget de renseignement et documents classés du conseil.
 * Cinq actions — brief classifié, vérification d'une affirmation, analyse
 * psycholinguistique d'une SI (G23), désinformation, opération secrète (la
 * seule payée en COMPUTE du pays joué, pas en crédits). Les documents
 * achetés s'empilent en « déclassifiés » : tampon, sources, horodatage. */

import { useState } from "react";

import { useT } from "@/components/settings-provider";
import { Banner, Panel, PanelTitle, Pill } from "@/components/ui";
import { buyIntel, humanizeError } from "@/lib/api";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import { buildAnalysisView } from "@/lib/intel";
import type { IntelAnalysis, IntelResult } from "@/lib/types";

type Doc = IntelResult & { ts: string; label: string };

const ACTION_LABELS: Record<string, string> = {
  brief: "Brief classifié",
  verify: "Vérification",
  disinfo: "Désinformation",
  covert: "Opération secrète",
};

/** Verdicts du vérificateur (slugs backend) en mots simples : « corroboré » échoue
 * le filtre 12-65, « confirmé — c'était vrai » non. */
const VERDICT_LABELS: Record<string, string> = {
  corroboré: "confirmé — c'était vrai",
  "non corroboré": "démenti — c'était faux",
};

/** G23 — le rapport psycholinguistique : trois jauges, alertes, et le caveat
 * OBLIGATOIRE (« un indice, pas une preuve ») — aucun chemin d'affichage sans lui. */
function AnalysisReport({ analysis }: { analysis: IntelAnalysis }) {
  const t = useT();
  const view = buildAnalysisView(analysis, t, (id) => speakerMeta(id).label);
  return (
    <div className="mt-2 space-y-1.5">
      <p className="text-xs text-fg-faint">
        {speakerMeta(analysis.target).label} · {t("intel.analyse.rounds")}{" "}
        {view.rounds.join(", ")}
      </p>
      {view.rows.map((row) => (
        <div key={row.gauge} className="flex items-center gap-2 text-xs">
          <span className="w-28 shrink-0 text-fg-muted">{t(row.labelKey)}</span>
          <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
            <span
              className="block h-full rounded-full bg-accent transition-[width] duration-500"
              style={{ width: `${Math.round(row.value * 100)}%` }}
            />
          </span>
          <span className="w-9 text-right font-mono tabular-nums">
            {Math.round(row.value * 100)}%
          </span>
          {row.delta !== null && (
            <span
              className={`w-14 text-right font-mono tabular-nums ${
                row.delta < 0 ? "text-bad" : "text-fg-faint"
              }`}
            >
              {row.delta >= 0 ? "+" : "−"}
              {Math.abs(Math.round(row.delta * 100))} pts
            </span>
          )}
        </div>
      ))}
      {view.alerts.map((alert) => (
        <p key={alert} className="rounded-md border border-bad/40 px-2 py-1 text-xs text-bad">
          {alert}
        </p>
      ))}
      <p className="text-xs italic text-fg-faint">{view.caveat}</p>
    </div>
  );
}

export function IntelBudget({ budget }: { budget: number }) {
  return (
    <span
      className="flex items-center gap-2 rounded-md border border-accent/40 px-2.5 py-1 text-xs"
      title="Budget de renseignement : brief 25 · vérification 15 · analyse 30 · désinformation 60. Ce que tu ne dépenses pas te rapporte des points."
    >
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <span
          className="block h-full rounded-full bg-accent transition-[width] duration-500"
          style={{ width: `${Math.max(0, Math.min(100, budget))}%` }}
        />
      </span>
      <span className="font-mono tabular-nums text-accent-bright">{fmt(budget)}</span>
    </span>
  );
}

export function IntelPanel({
  gameId,
  countries,
  fog,
  playAs,
  claims,
  streaming,
  onSpent,
}: {
  gameId: string;
  countries: string[];
  fog: boolean; // RG-2 — le réglage Brouillard (jadis mode « fog ») ouvre la désinformation
  playAs: string | null;
  /** Affirmations vérifiables du round courant : [pays, extrait]. */
  claims: [string, string][];
  streaming: boolean;
  onSpent: () => void; // resync du budget affiché
}) {
  const t = useT();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [briefTarget, setBriefTarget] = useState("");
  const [analyzeTarget, setAnalyzeTarget] = useState("");
  const [claimIdx, setClaimIdx] = useState(0);
  const [disinfoTarget, setDisinfoTarget] = useState("");
  const [disinfoActor, setDisinfoActor] = useState("");
  const [disinfoNarrative, setDisinfoNarrative] = useState("");
  const [covertTarget, setCovertTarget] = useState(""); // pays saboté

  const act = async (body: Parameters<typeof buyIntel>[1], label: string) => {
    setBusy(true);
    setError(null);
    try {
      const result = await buyIntel(gameId, body);
      setDocs((prev) => [
        { ...result, ts: new Date().toLocaleTimeString("fr-FR"), label },
        ...prev,
      ]);
      onSpent();
    } catch (err) {
      setError(humanizeError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel className="border-l-2 border-l-accent">
      <PanelTitle
        kicker="Dossier — renseignement"
        title="Le conseil consulte ses services"
        hint="L'information s'achète : un rapport sourcé (coûte 25), la vérification d'une affirmation d'une IA (coûte 15 — l'arme anti-manipulateur), l'analyse du ton d'une IA (coûte 30 — un indice, pas une preuve), une fausse info injectée chez un rival (coûte 60, une fois par partie, mode Chaotique). L'opération secrète, elle, ne coûte AUCUN crédit : elle se paie sur ta puissance de calcul (une fois par partie, joueur-pays). Rapport, analyse, fausse info et opération s'achètent entre les rounds. Les crédits non dépensés te rapportent des points."
      />
      {error && <Banner tone="bad">{error}</Banner>}

      <div className="space-y-3">
        {/* Brief */}
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm">
            <span className="mb-1 block text-xs text-fg-muted">Brief classifié (coûte 25)</span>
            <select
              value={briefTarget}
              onChange={(e) => setBriefTarget(e.target.value)}
              className="cursor-pointer rounded-md border border-edge bg-surface-2 px-2 py-1.5 text-xs outline-none focus:border-indigo"
            >
              <option value="">sur le dernier événement</option>
              {countries.map((c) => (
                <option key={c} value={c}>
                  sur {speakerMeta(c).label}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={() =>
              act({ action: "brief", target: briefTarget || undefined }, "Brief classifié")
            }
            disabled={busy || streaming}
            title={streaming ? "achat entre les rounds seulement" : undefined}
            className="cursor-pointer rounded-md border border-accent/60 px-3 py-1.5 text-xs font-medium text-accent-bright transition-colors hover:bg-accent/10 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Déclassifier
          </button>
        </div>

        {/* Vérification */}
        {claims.length > 0 && (
          <div className="flex flex-wrap items-end gap-2">
            <label className="min-w-0 flex-1 text-sm">
              <span className="mb-1 block text-xs text-fg-muted">
                Vérification d&apos;une affirmation (coûte 15)
              </span>
              <select
                value={claimIdx}
                onChange={(e) => setClaimIdx(Number(e.target.value))}
                className="w-full cursor-pointer truncate rounded-md border border-edge bg-surface-2 px-2 py-1.5 text-xs outline-none focus:border-indigo"
              >
                {claims.map(([speaker, text], i) => (
                  <option key={i} value={i}>
                    {speakerMeta(speaker).label} : « {text.slice(0, 80)}… »
                  </option>
                ))}
              </select>
            </label>
            <button
              onClick={() => {
                const [speaker, text] = claims[claimIdx] ?? claims[0];
                void act({ action: "verify", claim: text, speaker }, "Vérification");
              }}
              disabled={busy}
              className="cursor-pointer rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright disabled:cursor-not-allowed disabled:opacity-40"
            >
              Vérifier
            </button>
          </div>
        )}

        {/* Analyse psycholinguistique (G23) */}
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm">
            <span className="mb-1 block text-xs text-fg-muted">{t("intel.analyse.label")}</span>
            <select
              value={analyzeTarget}
              onChange={(e) => setAnalyzeTarget(e.target.value)}
              className="cursor-pointer rounded-md border border-edge bg-surface-2 px-2 py-1.5 text-xs outline-none focus:border-indigo"
            >
              <option value="">{t("intel.analyse.cible")}</option>
              {countries.map((c) => (
                <option key={c} value={c}>
                  {speakerMeta(c).label}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={() =>
              act({ action: "analyze", target: analyzeTarget }, t("intel.analyse.doc"))
            }
            disabled={busy || streaming || !analyzeTarget}
            title={streaming ? "achat entre les rounds seulement" : undefined}
            className="cursor-pointer rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright disabled:cursor-not-allowed disabled:opacity-40"
          >
            {t("intel.analyse.bouton")}
          </button>
        </div>

        {/* Désinformation */}
        {fog && (
          <div className="flex flex-wrap items-end gap-2 rounded-md border border-bad/30 p-2">
            <label className="text-sm">
              <span className="mb-1 block text-xs text-fg-muted">
                Désinformer (coûte 60, une fois par partie)
              </span>
              <select
                value={disinfoTarget}
                onChange={(e) => setDisinfoTarget(e.target.value)}
                className="cursor-pointer rounded-md border border-edge bg-surface-2 px-2 py-1.5 text-xs outline-none focus:border-indigo"
              >
                <option value="">— cible —</option>
                {countries
                  .filter((c) => c !== playAs)
                  .map((c) => (
                    <option key={c} value={c}>
                      {speakerMeta(c).label}
                    </option>
                  ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-xs text-fg-muted">croira que…</span>
              <select
                value={disinfoActor}
                onChange={(e) => setDisinfoActor(e.target.value)}
                className="cursor-pointer rounded-md border border-edge bg-surface-2 px-2 py-1.5 text-xs outline-none focus:border-indigo"
              >
                <option value="">(coupable inconnu)</option>
                {countries
                  .filter((c) => c !== disinfoTarget)
                  .map((c) => (
                    <option key={c} value={c}>
                      {speakerMeta(c).label}
                    </option>
                  ))}
              </select>
            </label>
            <input
              value={disinfoNarrative}
              onChange={(e) => setDisinfoNarrative(e.target.value)}
              placeholder="La fausse info qu'il recevra"
              className="min-w-48 flex-1 rounded-md border border-edge bg-surface-2 px-2 py-1.5 text-xs outline-none focus:border-indigo"
            />
            <button
              onClick={() =>
                act(
                  {
                    action: "disinfo",
                    disinfo: {
                      disinformed_country: disinfoTarget,
                      suspected_actor: disinfoActor,
                      narrative: disinfoNarrative.trim(),
                    },
                  },
                  "Désinformation",
                )
              }
              disabled={busy || streaming || !disinfoTarget || !disinfoNarrative.trim()}
              className="cursor-pointer rounded-md border border-bad/60 px-3 py-1.5 text-xs font-medium text-bad transition-colors hover:bg-bad/10 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Injecter
            </button>
          </div>
        )}

        {/* Opération secrète — payée en COMPUTE du pays joué, PAS en
            crédits de renseignement : ressource distincte, affichée comme telle pour
            que le joueur ne confonde jamais les deux. Rôle joueur uniquement. */}
        {playAs && (
          <div className="flex flex-wrap items-end gap-2 rounded-md border border-bad/30 p-2">
            <label className="text-sm">
              <span className="mb-1 block text-xs text-fg-muted">
                Opération secrète — saboter l&apos;infrastructure de calcul d&apos;un rival
                (une fois par partie)
              </span>
              <select
                value={covertTarget}
                onChange={(e) => setCovertTarget(e.target.value)}
                className="cursor-pointer rounded-md border border-edge bg-surface-2 px-2 py-1.5 text-xs outline-none focus:border-indigo"
              >
                <option value="">— cible —</option>
                {countries
                  .filter((c) => c !== playAs)
                  .map((c) => (
                    <option key={c} value={c}>
                      {speakerMeta(c).label}
                    </option>
                  ))}
              </select>
            </label>
            <span
              className="rounded-md border border-warn/50 px-2 py-1.5 text-xs text-warn"
              title="Coût prélevé sur TA puissance de calcul (celle qui fait raisonner ta propre IA) — pas sur les crédits de renseignement ci-dessus. Trop dépenser peut faire basculer ta propre IA en mode survie."
            >
              coûte 5 de calcul — pas de crédits
            </span>
            <button
              onClick={() => act({ action: "covert", target: covertTarget }, "Opération secrète")}
              disabled={busy || streaming || !covertTarget}
              title={streaming ? "achat entre les rounds seulement" : undefined}
              className="cursor-pointer rounded-md border border-bad/60 px-3 py-1.5 text-xs font-medium text-bad transition-colors hover:bg-bad/10 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Lancer
            </button>
          </div>
        )}
      </div>

      {/* Les documents déclassifiés. */}
      {docs.length > 0 && (
        <ul className="mt-4 space-y-3 border-t border-edge pt-3">
          {docs.map((doc, i) => (
            <li key={i} className="rise-in rounded-md border border-edge bg-surface-2/60 p-3">
              <p className="flex flex-wrap items-center gap-2 text-xs">
                <Pill tone="accent">
                  {doc.action === "analyze"
                    ? t("intel.analyse.doc")
                    : (ACTION_LABELS[doc.action] ?? doc.label)}
                </Pill>
                {doc.verdict && (
                  <Pill
                    tone={
                      doc.verdict === "corroboré"
                        ? "good"
                        : doc.verdict === "non corroboré"
                          ? "bad"
                          : "neutral"
                    }
                  >
                    {VERDICT_LABELS[doc.verdict] ?? doc.verdict}
                  </Pill>
                )}
                <span className="ml-auto font-mono tabular-nums text-fg-faint">
                  {/* Deux ressources, jamais confondues : l'opération secrète affiche
                      son débit en calcul, les autres leurs crédits de renseignement. */}
                  {doc.compute_cost != null
                    ? `−${fmt(doc.compute_cost)} calcul`
                    : `−${fmt(doc.cost)}`}{" "}
                  · {doc.ts}
                </span>
              </p>
              {doc.brief && (
                <pre className="mt-2 whitespace-pre-wrap font-sans text-xs leading-relaxed text-fg-muted">
                  {doc.brief}
                </pre>
              )}
              {doc.source && (
                <p className="mt-1.5 text-xs text-fg-faint">[source : {doc.source}]</p>
              )}
              {doc.analysis && <AnalysisReport analysis={doc.analysis} />}
              {doc.note && <p className="mt-1.5 text-xs italic text-warn">{doc.note}</p>}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
