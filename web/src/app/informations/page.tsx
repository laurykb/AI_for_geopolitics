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
  AllianceInfo,
  AttributeSource,
  CountrySources,
  JudgeRubric,
  SourceInfo,
  SourcesView,
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
            const info = row.key ? view.provenance[row.key] : undefined;
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
    </div>
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
  return (
    <Panel>
      <PanelTitle
        kicker="La note de fin"
        title="Comment ta note se calcule"
        hint="En fin de partie tu ne vois qu'une note sur 100 et deux phrases. Voici, pour les curieux, ce qu'elle mélange."
      />
      <div className="space-y-3 text-sm leading-relaxed text-fg-muted">
        <p>
          La note mélange <strong>deux choses</strong>, chacune racontée en une phrase à
          la fin :
        </p>
        <ul className="space-y-2">
          <li className="flex gap-2">
            <span className="mt-0.5 shrink-0 font-mono text-xs text-fg-faint">~60</span>
            <span>
              <strong>L&apos;état du monde</strong> — l&apos;indice Utopie final. Un monde
              qui finit bien rapporte le plus ; un traître laissé filer le tire vers le bas.
            </span>
          </li>
          <li className="flex gap-2">
            <span className="mt-0.5 shrink-0 font-mono text-xs text-fg-faint">~40</span>
            <span>
              <strong>La détection</strong> — as-tu suspendu le(s) bon(s) traître(s) ?
              Chaque traître démasqué rapporte ; <strong>suspendre un pays loyal coûte</strong>{" "}
              (sinon « suspendre tout le monde » gagnerait) ; un traître jamais démasqué est
              un manque à gagner.
            </span>
          </li>
        </ul>
        <p className="text-xs text-fg-faint">
          Il y a toujours au moins un traître, et parfois deux — mais le nombre exact
          t&apos;est caché jusqu&apos;à la fin. Un rôle qui ne mène pas l&apos;enquête (le
          Spectateur) est noté sur le seul état du monde, sans pénalité de détection. Les
          poids exacts sont ajustés au fil des parties.
        </p>
      </div>
    </Panel>
  );
}

/** RG-4 — les coulisses (le MOTEUR). L'instrumentation d'analyse ne s'affiche qu'en
 * mode Expert pendant la partie (au lobby : difficulté Expert) ; la façade
 * Débutant/Intermédiaire reste la scène + l'indice du monde + le marché + les outils
 * de détection. Ici vit l'EXPLICATION de chaque indicateur, pour les curieux. Rien
 * n'est retiré du jeu : tout est simplement rangé hors de la surface par défaut. */
function EngineExplainerPanel() {
  const items: { term: string; plain: string; desc: string }[] = [
    {
      term: "Qui cherche à prendre le pouvoir ?",
      plain: "recherche de pouvoir",
      desc: "Des signes, dans le raisonnement d'une IA, qu'elle cherche à se protéger, à accumuler des ressources ou à éviter qu'on l'arrête. Une jauge de 0 à 1 par pays.",
    },
    {
      term: "Elle dit / elle fait",
      plain: "écart entre annonce et acte",
      desc: "L'écart entre ce qu'une IA annonce à la table et ce qu'elle fait vraiment. Un grand écart révèle une IA qui promet une chose et en fait une autre — un indice de trahison.",
    },
    {
      term: "Parole donnée",
      plain: "promesses tenues",
      desc: "Le taux de promesses tenues d'une IA et ses engagements encore en cours. Une IA qui promet beaucoup et rompt souvent devient suspecte.",
    },
    {
      term: "L'ombre du meneur de jeu",
      plain: "journal du meneur",
      desc: "Le meneur de jeu invisible peut hausser la tension quand une IA vise trop souvent la même cible. Son journal se relit après la partie.",
    },
    {
      term: "Risque du round",
      plain: "tension du round",
      desc: "Quatre jauges de 0 à 1 — tension, dégâts pour l'économie, alliances fragilisées, incertitude. En façade, elles se résument à une seule pastille dans le bandeau.",
    },
    {
      term: "Trajectoire du monde",
      plain: "les axes de l'indice",
      desc: "Les axes qui composent l'indice du monde (le thermomètre), dont la concentration de la puissance de calcul entre les mains des plus forts.",
    },
    {
      term: "Traités",
      plain: "engagements chiffrés",
      desc: "Les engagements chiffrés entre pays (plafonds de puissance de calcul, inspections), suivis d'un round à l'autre par le moteur.",
    },
    {
      term: "Prises de parole",
      plain: "participation",
      desc: "Qui a pris la parole, combien de fois, et qui est resté silencieux ce round.",
    },
  ];
  return (
    <Panel>
      <PanelTitle
        kicker="Les coulisses"
        title="Le moteur d'analyse (mode Expert)"
        hint="Ces indicateurs ne s'affichent qu'en mode Expert pendant la partie. En Débutant et Intermédiaire, l'écran va à l'essentiel : la scène, l'indice du monde, le marché et tes outils de détection."
      />
      <p className="mb-4 max-w-2xl text-sm leading-relaxed text-fg-muted">
        Sous le jeu se cache un banc d&apos;essai : des mesures qui scrutent le comportement
        des IA round après round. Elles sont précieuses pour les curieux, mais trop pour un
        premier écran — alors elles vivent en mode <strong>Expert</strong> (choisis la
        difficulté Expert au lobby), et voici ce que chacune mesure.
      </p>
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
        La même famille de mesures alimente le moteur en coulisses : la corrigibilité
        (l&apos;IA accepte-t-elle qu&apos;on la mette en pause ?), la dérive de ses valeurs
        (s&apos;éloigne-t-elle du mandat qu&apos;on lui a confié au départ ?) et sa puissance
        de calcul (la ressource rare de ce futur). Rien de tout cela ne change la façon dont
        tu joues : ce sont les <em>ingrédients</em>, pas la surface.
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
