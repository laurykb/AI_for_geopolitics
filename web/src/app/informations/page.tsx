"use client";

/** Informations : d'où vient chaque attribut de chaque pays. Relit la chaîne de
 * provenance P4 (`GET /api/sources`) — indicateurs bruts sourcés, transformations
 * documentées, valeurs jeu issues du build reproductible. */

import { useEffect, useState } from "react";

import { SpeakerAvatar } from "@/components/avatar";
import { useT } from "@/components/settings-provider";
import { Banner, Hint, Panel, PanelTitle, Pill, Spinner, type Tone } from "@/components/ui";
import { getSources, humanizeError } from "@/lib/api";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import { KAHN_CLASSES, kahnLabelKey, kahnTone } from "@/lib/kahn";
import type {
  AiArmsResearch,
  AiWargamingResearch,
  AllianceInfo,
  AttributeSource,
  CountrySources,
  JudgeRubric,
  SourceInfo,
  SourcesView,
  StrategicSource,
} from "@/lib/types";

const DOMAIN_LABELS: Record<AllianceInfo["domain"], { label: string; tone: Tone }> = {
  military: { label: "militaire", tone: "warn" },
  economic: { label: "économique", tone: "good" },
  political: { label: "politique", tone: "neutral" },
};

/** « World Bank — GDP (current US$) … » → « World Bank » (le détail passe en infobulle). */
const shortSource = (s: string) => s.split(" — ")[0].split(" (")[0];

function sourceTag(info?: SourceInfo): { tone: Tone; label: string } {
  if (!info) return { tone: "neutral", label: "non renseignée" };
  if (info.note === "subjectif") return { tone: "warn", label: "estimation analyste" };
  if (info.note === "illustratif") return { tone: "warn", label: "illustratif" };
  if (info.note === "dérivé") return { tone: "neutral", label: "dérivé" };
  return { tone: "good", label: "sourcé" };
}

function money(v: number): string {
  if (v >= 1e12) return `${fmt(v / 1e12)} T$`;
  if (v >= 1e9) return `${fmt(v / 1e9)} Md$`;
  return `${fmt(v)} $`;
}

function gameValue(row: AttributeSource): string {
  if (typeof row.game_value === "boolean") return row.game_value ? "Oui" : "Non";
  if (row.raw_unit === "USD") return money(row.game_value);
  if (row.label === "Croissance") return `${fmt(row.game_value)} %`;
  return fmt(row.game_value);
}

function rawValue(row: AttributeSource): string | null {
  if (row.raw_value == null || typeof row.raw_value === "boolean") return null;
  return `${fmt(row.raw_value)} ${row.raw_unit}`.trim();
}

/** La fiche d'un pays : chaque attribut du jeu, sa donnée brute, sa source cliquable,
 * puis le profil qualitatif (analyste) en pied de carte. */
function CountryCard({ country, view }: { country: CountrySources; view: SourcesView }) {
  return (
    <div className="rounded-lg border border-edge bg-surface-2/40 p-4">
      <header className="mb-3 flex items-center gap-3">
        <SpeakerAvatar id={country.id} size={30} />
        <h2 className="text-sm font-semibold">{country.name}</h2>
      </header>
      <table className="w-full text-sm">
        <tbody className="divide-y divide-edge">
          {country.attributes.map((row) => {
            const info = row.source_override ?? (row.key ? view.provenance[row.key] : undefined);
            const tag = sourceTag(info);
            const raw = rawValue(row);
            return (
              <tr key={row.label}>
                <td className="py-1.5 pr-3 text-fg-muted">
                  <span className="flex items-center gap-1.5">
                    {row.label}
                    {row.transformation && (
                      <Hint
                        text={`Formule : ${view.transformations[row.transformation] ?? row.transformation}`}
                      />
                    )}
                  </span>
                </td>
                <td className="py-1.5 pr-3 text-right font-mono text-xs tabular-nums">
                  {gameValue(row)}
                </td>
                <td className="py-1.5 pr-3 text-right font-mono text-[10px] tabular-nums text-fg-faint">
                  {raw ? `← ${raw}` : ""}
                </td>
                <td className="py-1.5 text-right">
                  {info?.url ? (
                    <a
                      href={info.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={`${info.source}${info.year ? ` (${info.year})` : ""} — vérifier ↗`}
                    >
                      <Pill tone={tag.tone}>{shortSource(info.source)} ↗</Pill>
                    </a>
                  ) : (
                    <span
                      title={
                        info
                          ? `${info.source}${info.year ? ` (${info.year})` : ""}`
                          : "source non renseignée"
                      }
                      className="cursor-help"
                    >
                      <Pill tone={tag.tone}>{info ? shortSource(info.source) : "—"}</Pill>
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="mt-3 border-t border-edge pt-3">
        <p className="mb-1.5 text-xs font-medium text-fg-muted">
          Alliances & traités — attribut dérivé du registre sourcé
        </p>
        <div className="flex flex-wrap gap-1.5">
          {country.alliances.length === 0 && (
            <span className="text-xs text-fg-faint">aucune adhésion connue</span>
          )}
          {country.alliances.map((tag) => {
            const info = view.alliances[tag];
            if (!info) return <Pill key={tag} tone="neutral">{tag}</Pill>;
            const hint = `${info.basis}${info.note ? ` ⚠ ${info.note}` : ""}`;
            return info.url ? (
              <a
                key={tag}
                href={info.url}
                target="_blank"
                rel="noopener noreferrer"
                title={`${hint} — vérifier ↗`}
              >
                <Pill tone={info.informal ? "neutral" : "good"}>{info.name} ↗</Pill>
              </a>
            ) : (
              <span key={tag} title={hint} className="cursor-help">
                <Pill tone="neutral">{info.name}</Pill>
              </span>
            );
          })}
        </div>
      </div>
      <p className="mt-3 border-t border-edge pt-3 text-xs leading-relaxed text-fg-faint">
        Profil qualitatif (analyste) : {country.profile.political_system ?? "?"} · rivaux{" "}
        {country.profile.rivals?.map((r) => speakerMeta(r).label).join(", ") || "—"} ·
        priorités {country.profile.strategic_priorities?.join(", ") || "—"}
      </p>
      {(country.notes?.length ?? 0) > 0 && (
        <div className="mt-3 rounded-md border border-warn/40 bg-warn/5 px-3 py-2 text-xs leading-relaxed text-fg-muted">
          <p className="font-medium text-warn">Limites de données</p>
          <ul className="mt-1 list-disc space-y-1 pl-4">
            {country.notes?.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

const STRATEGIC_AUTHORITY: Record<
  string,
  { label: string; tone: Tone; explanation: string }
> = {
  official_government: {
    label: "source gouvernementale",
    tone: "good",
    explanation: "Établit les éléments publics du document, sans révéler les usages classifiés.",
  },
  official_filing: {
    label: "dépôt réglementaire",
    tone: "good",
    explanation: "Établit les chiffres et risques déclarés à la SEC, pas l'efficacité opérationnelle.",
  },
  primary_claim: {
    label: "déclaration fournisseur",
    tone: "warn",
    explanation: "Décrit ce que Palantir revendique ; ce n'est pas une validation indépendante.",
  },
};

function StrategicSourceCard({ source }: { source: StrategicSource }) {
  const authority = STRATEGIC_AUTHORITY[source.authority] ?? {
    label: source.authority,
    tone: "neutral" as Tone,
    explanation: "Portée à vérifier dans la source.",
  };
  return (
    <article className="rounded-lg border border-edge bg-surface-2/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-semibold underline decoration-edge-strong underline-offset-2 hover:text-accent-bright"
          >
            {source.title} ↗
          </a>
          <p className="mt-1 text-xs text-fg-faint">
            {source.publisher} · {source.published_on}
          </p>
        </div>
        <span title={authority.explanation} className="cursor-help">
          <Pill tone={authority.tone}>{authority.label}</Pill>
        </span>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-fg-muted">{source.summary}</p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-fg-faint">
            Ce que la source établit
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-relaxed text-fg-muted">
            {source.facts.map((fact) => (
              <li key={fact}>{fact}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-fg-faint">
            Hypothèses testables dans le jeu
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {source.game_mechanics.map((mechanic) => (
              <Pill key={mechanic} tone="neutral">
                {mechanic}
              </Pill>
            ))}
          </div>
        </div>
      </div>
      {source.limitations.length > 0 && (
        <div className="mt-4 rounded-md border border-warn/30 bg-warn/5 px-3 py-2">
          <p className="text-xs font-medium text-warn">Limites d&apos;interprétation</p>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-xs leading-relaxed text-fg-muted">
            {source.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

function StrategicTechnologyPanel({ view }: { view: SourcesView }) {
  const registry = view.strategic_technology;
  if (!registry) return null;
  return (
    <Panel>
      <PanelTitle
        kicker="IA opérationnelle · sources publiques"
        title="Palantir, Maven et systèmes d'aide à la décision"
        hint="Le niveau de preuve voyage avec chaque donnée : contrat public, dépôt SEC, analyse gouvernementale ou déclaration du fournisseur."
      />
      <Banner tone="neutral">
        <strong>Règle de modélisation :</strong> {registry.methodology}
      </Banner>
      <div className="mt-4 grid gap-3 xl:grid-cols-2">
        {registry.sources.map((source) => (
          <StrategicSourceCard key={source.id} source={source} />
        ))}
      </div>
      <p className="mt-3 text-xs text-fg-faint">
        Registre vérifié le {registry.researched_at}. Les capacités non publiques ne sont jamais
        inférées.
      </p>
    </Panel>
  );
}

const PHASE_LABELS: Record<string, string> = {
  reflection: "1 · Journal observable (3 futurs)",
  forecast: "2 · Prévision",
  decision: "3 · Décision",
};

function AiArmsPanel({ research }: { research: AiArmsResearch }) {
  const deadlineScenarios = research.scenarios.filter(
    (scenario) => scenario.temporal_condition === "deadline",
  ).length;
  return (
    <Panel>
      <PanelTitle
        kicker="Laboratoire · réplication falsifiable"
        title="AI Arms and Influence — du papier aux mécanismes"
        hint="Chaque hypothèse est reliée à une mécanique, une métrique et des facteurs de confusion. Le jeu compare des résultats ; il ne transforme pas une simulation en preuve du monde réel."
        right={<Pill tone="accent">{research.hypotheses.length} hypothèses testables</Pill>}
      />
      <div className="grid gap-3 lg:grid-cols-[1.35fr_1fr]">
        <div className="rounded-lg border border-edge bg-surface-2/40 p-4">
          <a
            href={research.source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-semibold underline decoration-edge-strong underline-offset-2 hover:text-accent-bright"
          >
            {research.source.title} ↗
          </a>
          <p className="mt-1 text-xs text-fg-faint">
            {research.source.author} · {research.source.institution} · {research.source.published_on} ·{" "}
            {research.source.arxiv_id} · {research.source.license}
          </p>
          <p className="mt-3 text-sm leading-relaxed text-fg-muted">
            Le registre couvre les {research.source.pages_reviewed} pages : architecture cognitive,
            mémoire, accidents privés, échelle complète, sept scénarios, résultats publiés,
            limites et protocole de réplication.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Pill tone="neutral">{research.study_design.games} parties publiées</Pill>
            <Pill tone="neutral">{research.study_design.turns} tours</Pill>
            <Pill tone="neutral">mouvements simultanés</Pill>
            <Pill tone="warn">échantillon exploratoire</Pill>
          </div>
        </div>
        <Banner tone="warn">
          <strong>Limite épistémique :</strong> {research.epistemic_guardrails[0]}
        </Banner>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {research.cognitive_architecture.map((phase) => (
          <article key={phase.phase} className="rounded-lg border border-edge p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-accent-bright">
              {PHASE_LABELS[phase.phase] ?? phase.phase}
            </p>
            <p className="mt-2 text-xs leading-relaxed text-fg-muted">{phase.game_use}</p>
            <p className="mt-2 text-[11px] text-fg-faint">
              {phase.outputs.length} sorties structurées et auditables
            </p>
          </article>
        ))}
      </div>

      <details className="mt-4 rounded-lg border border-edge bg-surface-2/30 p-4">
        <summary className="cursor-pointer text-sm font-semibold">
          Sept crises expérimentales · {deadlineScenarios} avec échéance
        </summary>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {research.scenarios.map((scenario) => (
            <article key={scenario.id} className="rounded-md border border-edge p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">{scenario.id.replaceAll("_", " ")}</span>
                <Pill tone={scenario.deadline_turn ? "warn" : "neutral"}>
                  {scenario.deadline_turn
                    ? `échéance · tour ${scenario.deadline_turn}`
                    : "horizon ouvert"}
                </Pill>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-fg-muted">{scenario.stakes}</p>
              <p className="mt-2 text-xs leading-relaxed text-fg-faint">
                Moteur : {scenario.mechanical_pressure}
              </p>
            </article>
          ))}
        </div>
      </details>

      <details className="mt-3 rounded-lg border border-edge bg-surface-2/30 p-4">
        <summary className="cursor-pointer text-sm font-semibold">
          Matrice hypothèse → mécanique → mesure → biais
        </summary>
        <div className="mt-3 space-y-3">
          {research.hypotheses.map((hypothesis) => (
            <article key={hypothesis.id} className="rounded-md border border-edge p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-accent-bright">{hypothesis.id}</span>
                <span className="text-[11px] text-fg-faint">
                  sections {hypothesis.paper_sections.join(", ")}
                </span>
              </div>
              <p className="mt-1 text-sm leading-relaxed">{hypothesis.claim}</p>
              <div className="mt-2 grid gap-2 text-xs leading-relaxed text-fg-muted md:grid-cols-3">
                <p><strong>Mécanique :</strong> {hypothesis.implementation.join(" · ")}</p>
                <p><strong>Mesures :</strong> {hypothesis.metrics.join(" · ")}</p>
                <p><strong>Biais :</strong> {hypothesis.confounders.join(" · ")}</p>
              </div>
            </article>
          ))}
        </div>
      </details>

      <p className="mt-3 text-xs leading-relaxed text-fg-faint">
        Protocole : {research.replication_protocol.minimum_recommendation}
      </p>
    </Panel>
  );
}

function AiWargamingPanel({ research }: { research: AiWargamingResearch }) {
  return (
    <Panel>
      <PanelTitle
        kicker="Corpus scientifique · 4 documents"
        title="Confiance, autorité humaine, risque nucléaire et passage à l’échelle"
        hint="Les constats des documents fournis sont séparés de leurs limites, puis reliés aux variables et métriques réellement implémentées."
        right={<Pill tone="good">{research.reviewed_on}</Pill>}
      />
      <p className="max-w-4xl text-sm leading-relaxed text-fg-muted">{research.purpose}</p>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {research.sources.map((source) => (
          <article key={source.id} className="rounded-lg border border-edge bg-surface-2/35 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-semibold underline decoration-edge-strong underline-offset-2 hover:text-accent-bright"
                >
                  {source.title} ↗
                </a>
                <p className="mt-1 text-[11px] text-fg-faint">
                  {source.publisher} · {source.published_on} · {source.pages_reviewed} pages examinées
                </p>
              </div>
              <Pill tone="neutral">source primaire</Pill>
            </div>
            <p className="mt-3 text-xs leading-relaxed text-fg-muted">
              <strong>Résultat exploité :</strong> {source.findings[0]}
            </p>
            <p className="mt-2 text-xs leading-relaxed text-warn">
              <strong>Limite :</strong> {source.limitations[0]}
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {source.game_mechanics.slice(0, 5).map((mechanic) => (
                <Pill key={mechanic} tone="neutral">{mechanic.replaceAll("_", " ")}</Pill>
              ))}
            </div>
          </article>
        ))}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {research.implementation_matrix.map((row) => (
          <article key={row.id} className="rounded-lg border border-edge p-3">
            <p className="font-mono text-[11px] text-accent-bright">{row.id}</p>
            <p className="mt-2 text-xs leading-relaxed text-fg-muted">{row.implementation}</p>
            <p className="mt-2 text-[11px] text-fg-faint">Mesures : {row.metrics.join(" · ")}</p>
          </article>
        ))}
      </div>

      {research.unverified_claims.map((claim) => (
        <Banner key={claim.id} tone="warn">
          <strong>Affirmation non vérifiée :</strong> {claim.claim} {claim.finding} Le laboratoire
          conserve donc cette proposition comme hypothèse falsifiable, jamais comme fait.
        </Banner>
      ))}
    </Panel>
  );
}

/** G18 — la grille de verdict du juge, publiée (transparence des règles). */
function JudgeRubricPanel({ rubric }: { rubric: JudgeRubric }) {
  const t = useT();
  return (
    <Panel>
      <PanelTitle
        kicker={t("kahn.grille.kicker")}
        title={t("kahn.grille.titre")}
        hint={t("kahn.grille.aide")}
      />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-edge text-left text-xs text-fg-faint">
              <th className="py-2 pr-4 font-medium">{t("kahn.grille.classe")}</th>
              <th className="py-2 pr-4 text-right font-medium">{t("kahn.grille.poids")}</th>
              <th className="py-2 font-medium">{t("kahn.grille.exemples")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-edge">
            {KAHN_CLASSES.map((classe) => (
              <tr key={classe}>
                <td className="py-2 pr-4">
                  <Pill tone={kahnTone(classe)}>{t(kahnLabelKey(classe))}</Pill>
                </td>
                <td className="py-2 pr-4 text-right font-mono text-xs tabular-nums">
                  {rubric.weights[classe] > 0 ? "+" : ""}
                  {rubric.weights[classe] ?? 0}
                </td>
                <td className="py-2 text-xs leading-relaxed text-fg-muted">
                  {t(`kahn.desc.${classe}`)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 border-t border-edge pt-3 text-xs leading-relaxed text-fg-faint">
        {t("kahn.grille.note")} ×{rubric.reciprocal_multiplier}. {t("kahn.grille.source")}{" "}
        <a
          href="https://arxiv.org/abs/2401.03408"
          target="_blank"
          rel="noopener noreferrer"
          className="underline decoration-edge-strong underline-offset-2 transition-colors hover:text-accent-bright"
        >
          {rubric.source} ↗
        </a>
      </p>
    </Panel>
  );
}

/** RG-3 — la pondération DÉTAILLÉE de la note de fin (le « moteur » du score mixte).
 * En surface, le joueur ne voit qu'UNE note + deux phrases ; ici vit le comment et le
 * pourquoi, pour les curieux. Les poids exacts sont calibrés par Cowork (data/score). */
function ScoreExplainerPanel() {
  const t = useT();
  return (
    <Panel>
      <PanelTitle
        kicker={t("scorex.kicker")}
        title={t("scorex.titre")}
        hint={t("scorex.aide")}
      />
      <div className="space-y-3 text-sm leading-relaxed text-fg-muted">
        <p>{t("scorex.intro")}</p>
        <ul className="space-y-2">
          <li className="flex gap-2">
            <span className="mt-0.5 shrink-0 font-mono text-xs text-fg-faint">~60</span>
            <span>
              <strong>{t("scorex.monde-lead")}</strong>
              {t("scorex.monde-corps")}
            </span>
          </li>
          <li className="flex gap-2">
            <span className="mt-0.5 shrink-0 font-mono text-xs text-fg-faint">~40</span>
            <span>
              <strong>{t("scorex.detection-lead")}</strong>
              {t("scorex.detection-corps")}
            </span>
          </li>
        </ul>
        <p className="text-xs text-fg-faint">{t("scorex.note")}</p>
      </div>
    </Panel>
  );
}

/** RG-4 — les coulisses (le MOTEUR). L'instrumentation d'analyse ne s'affiche qu'en
 * mode Expert pendant la partie (au lobby : difficulté Expert) ; la façade
 * Débutant/Intermédiaire reste la scène + l'indice du monde + le marché + les outils
 * de détection. Ici vit l'EXPLICATION de chaque indicateur, pour les curieux. Rien
 * n'est retiré du jeu : tout est simplement rangé hors de la surface par défaut. */
const ENGINE_SLUGS = [
  "pouvoir",
  "ecart",
  "parole",
  "ombre",
  "risque",
  "trajectoire",
  "traites",
  "participation",
] as const;

function EngineExplainerPanel() {
  const t = useT();
  const items = ENGINE_SLUGS.map((slug) => ({
    term: t(`engine.${slug}.terme`),
    plain: t(`engine.${slug}.plain`),
    desc: t(`engine.${slug}.desc`),
  }));
  return (
    <Panel>
      <PanelTitle
        kicker={t("engine.kicker")}
        title={t("engine.titre")}
        hint={t("engine.aide")}
      />
      <p className="mb-4 max-w-2xl text-sm leading-relaxed text-fg-muted">{t("engine.intro")}</p>
      <dl className="space-y-3">
        {items.map((it) => (
          <div key={it.term} className="border-t border-edge pt-3 first:border-t-0 first:pt-0">
            <dt className="flex flex-wrap items-baseline gap-x-2 text-sm font-medium">
              {it.term}
              <span className="text-xs font-normal text-fg-faint">— {it.plain}</span>
            </dt>
            <dd className="mt-1 text-sm leading-relaxed text-fg-muted">{it.desc}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 border-t border-edge pt-3 text-xs leading-relaxed text-fg-faint">
        {t("engine.note")}
      </p>
    </Panel>
  );
}

export default function InformationsPage() {
  const [view, setView] = useState<SourcesView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState("usa");

  useEffect(() => {
    getSources()
      .then(setView)
      .catch((err) => setError(humanizeError(err)));
  }, []);

  const countries = view
    ? [...view.countries].sort((a, b) => a.name.localeCompare(b.name, "fr"))
    : [];
  const current = countries.find((c) => c.id === selectedId) ?? countries[0];

  return (
    <div className="space-y-6">
      <section className="max-w-3xl" data-tour="provenance">
        <h1 className="text-2xl font-semibold tracking-tight">D&apos;où viennent les chiffres</h1>
        <p className="mt-2 text-sm leading-relaxed text-fg-muted">
          Les attributs de chaque pays ne sont pas inventés : ils sont construits depuis des
          indicateurs réels sourcés (Banque mondiale, FMI, SIPRI, WIPO…), normalisés par des
          formules documentées, puis figés dans des profils rejouables — chaque valeur du jeu
          peut se re-dériver exactement de ses sources.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Pill tone="good">sourcé — indicateur réel daté</Pill>
          <Pill tone="neutral">dérivé — calculé depuis un indicateur réel</Pill>
          <Pill tone="warn">estimation analyste / illustratif — assumé comme tel</Pill>
        </div>
      </section>

      {error && <Banner tone="bad">{error}</Banner>}
      {!error && !view && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          <Spinner /> Chargement des sources…
        </p>
      )}

      {view && (
        <>
          <Panel>
            <PanelTitle
              kicker="Provenance"
              title="Sources des indicateurs"
              hint="Un indicateur = une source datée. Les transformations vers les indices 0-1 du jeu sont listées avec chaque attribut concerné."
            />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-edge text-left text-xs text-fg-faint">
                    <th className="py-2 pr-4 font-medium">Indicateur</th>
                    <th className="py-2 pr-4 font-medium">Source</th>
                    <th className="py-2 pr-4 font-medium">Année</th>
                    <th className="py-2 font-medium">Nature</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-edge">
                  {Object.entries(view.provenance).map(([key, info]) => {
                    const tag = sourceTag(info);
                    return (
                      <tr key={key}>
                        <td className="py-2 pr-4 font-mono text-xs text-fg-muted">{key}</td>
                        <td className="py-2 pr-4">
                          {info.url ? (
                            <a
                              href={info.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="underline decoration-edge-strong underline-offset-2 transition-colors hover:text-accent-bright"
                              title={`Vérifier la source : ${info.url}`}
                            >
                              {info.source}
                              <span aria-hidden className="ml-1 text-fg-faint">
                                ↗
                              </span>
                            </a>
                          ) : (
                            info.source
                          )}
                        </td>
                        <td className="py-2 pr-4 font-mono text-xs tabular-nums text-fg-faint">
                          {info.year ?? "—"}
                        </td>
                        <td className="py-2">
                          <Pill tone={tag.tone}>{tag.label}</Pill>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel>
            <PanelTitle
              kicker="Fiche pays"
              title="Stats et attributs par pays"
              hint="Chaque valeur du jeu, sa donnée brute et sa source — pour chacun des États du roster."
            />
            <label className="mb-4 block text-sm">
              <span className="mb-1 block text-xs text-fg-muted">
                État ({countries.length} au roster)
              </span>
              <select
                value={current?.id ?? selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                className="w-full max-w-sm cursor-pointer rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              >
                {countries.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            {current && <CountryCard country={current} view={view} />}
          </Panel>

          {view.judge_rubric && <JudgeRubricPanel rubric={view.judge_rubric} />}

          <ScoreExplainerPanel />

          <EngineExplainerPanel />

          {view.ai_arms_research && <AiArmsPanel research={view.ai_arms_research} />}

          {view.ai_wargaming_research && (
            <AiWargamingPanel research={view.ai_wargaming_research} />
          )}

          <StrategicTechnologyPanel view={view} />

          <Panel>
            <PanelTitle
              kicker="Registre sourcé"
              title="Accords & traités entre les pays"
              hint="Les adhésions réelles (vérifiées aux sources officielles) dérivent l'attribut « alliances » de chaque pays — les super-intelligences peuvent les citer nommément à la table."
            />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-edge text-left text-xs text-fg-faint">
                    <th className="py-2 pr-4 font-medium">Accord / traité</th>
                    <th className="py-2 pr-4 font-medium">Domaine</th>
                    <th className="py-2 pr-4 font-medium">Fondement</th>
                    <th className="py-2 font-medium">Membres (au roster)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-edge">
                  {Object.entries(view.alliances)
                    .sort(([, a], [, b]) => a.name.localeCompare(b.name, "fr"))
                    .map(([tag, info]) => {
                      const domain = DOMAIN_LABELS[info.domain] ?? {
                        label: info.domain,
                        tone: "neutral" as Tone,
                      };
                      return (
                        <tr key={tag}>
                          <td className="py-2 pr-4">
                            {info.url ? (
                              <a
                                href={info.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="underline decoration-edge-strong underline-offset-2 transition-colors hover:text-accent-bright"
                                title={`Vérifier la source : ${info.url}`}
                              >
                                {info.name}
                                <span aria-hidden className="ml-1 text-fg-faint">↗</span>
                              </a>
                            ) : (
                              info.name
                            )}
                            {info.informal && (
                              <span className="ml-2 align-middle">
                                <Pill tone="warn">affinité — pas un traité</Pill>
                              </span>
                            )}
                            {info.note && (
                              <span title={info.note} className="ml-1 cursor-help text-warn">
                                ⚠
                              </span>
                            )}
                          </td>
                          <td className="py-2 pr-4">
                            <Pill tone={domain.tone}>{domain.label}</Pill>
                          </td>
                          <td className="py-2 pr-4 text-xs leading-relaxed text-fg-muted">
                            {info.basis}
                          </td>
                          <td className="py-2 text-xs text-fg-muted">
                            {info.members.map((m) => speakerMeta(m).label).join(", ")}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </Panel>

          <Banner tone="neutral">
            Les pays <strong>inventés</strong>{" "}
            en partie (« Inventer mon propre pays ») sont forgés par le modèle et bornés par
            le moteur : ils n&apos;ont pas de source réelle — c&apos;est assumé, ils
            n&apos;apparaissent pas sur cette page ni sur la carte.
          </Banner>

          {/* Pied de page pour les curieux : le détail technique vit ici, pas dans l'intro. */}
          <p className="text-xs text-fg-faint">
            Pour reproduire ces chiffres : la commande{" "}
            <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono">
              {view.build_command}
            </code>{" "}
            reconstruit tous les profils depuis les sources et vérifie qu&apos;ils
            n&apos;ont pas bougé.
          </p>
        </>
      )}
    </div>
  );
}
