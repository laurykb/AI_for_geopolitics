"use client";

import { SpeakerAvatar } from "@/components/avatar";
import { Panel, PanelTitle, Pill, Switch } from "@/components/ui";
import { speakerMeta } from "@/lib/countries";
import type { ResearchModel } from "@/lib/types";

export function completeCountryAssignments(
  countries: string[],
  selectedModels: string[],
  current: Record<string, string> = {},
  humanCountry?: string | null,
): Record<string, string> {
  if (!selectedModels.length) return {};
  return [...new Set(countries)]
    .filter((country) => country !== humanCountry)
    .sort()
    .reduce<Record<string, string>>((result, country, index) => {
      const retained = current[country];
      result[country] = selectedModels.includes(retained)
        ? retained
        : selectedModels[index % selectedModels.length];
      return result;
    }, {});
}

export function ModelCastSelector({
  models,
  enabled,
  selected,
  onEnabled,
  onSelected,
  context,
}: {
  models: ResearchModel[];
  enabled: boolean;
  selected: string[];
  onEnabled: (enabled: boolean) => void;
  onSelected: (models: string[]) => void;
  context: "classic" | "campaign";
}) {
  const toggle = (tag: string) => {
    if (selected.includes(tag)) {
      onSelected(selected.filter((item) => item !== tag));
    } else if (selected.length < 4) {
      onSelected([...selected, tag]);
    }
  };
  const campaign = context === "campaign";

  return (
    <div data-tour="model-cast">
      <Panel className={enabled ? "border-accent/45 bg-accent/5" : ""}>
        <PanelTitle
          kicker={campaign ? "Campagne multi-IA" : "Casting des super-intelligences"}
          title="Faire dialoguer plusieurs modèles"
          hint={
            campaign
              ? "Le modèle unique ou le casting multi-IA est choisi explicitement puis figé dans chaque sauvegarde de chapitre."
              : "Choisissez explicitement le modèle unique, ou distribuez 2 à 4 modèles entre les pays, le Game Master et le juge."
          }
          right={<Pill tone={enabled ? "accent" : "neutral"}>{enabled ? `${selected.length} IA choisies` : "modèle unique"}</Pill>}
        />

        {!enabled && models.length > 0 && (
          <label className="mb-4 block rounded-lg border border-accent/35 bg-accent/5 p-3 text-xs text-fg-muted">
            <span className="block font-semibold text-foreground">Modèle unique de la partie</span>
            <span className="mt-1 block text-[11px] text-fg-faint">
              Ce choix pilotera tous les pays IA, le Game Master et le juge ; il sera enregistré dans la sauvegarde.
            </span>
            <select
              aria-label="Modèle unique de la partie"
              value={selected[0] ?? ""}
              onChange={(event) =>
                onSelected([
                  event.target.value,
                  ...selected.filter((tag) => tag !== event.target.value),
                ])
              }
              className="mt-2 w-full rounded-md border border-edge bg-surface-2 px-3 py-2 font-mono text-xs outline-none focus:border-accent-bright"
            >
              {models.map((model) => (
                <option key={model.tag} value={model.tag}>
                  {model.family} · {model.tag}
                </option>
              ))}
            </select>
          </label>
        )}

        <div className="mb-4 grid gap-2 sm:grid-cols-[1fr_auto_1fr_auto_1fr] sm:items-center">
          <CastRole label="Pays IA" detail="répartis équitablement" />
          <span aria-hidden="true" className="hidden text-accent-bright sm:block">→</span>
          <CastRole label="Game Master" detail="injecte les crises" />
          <span aria-hidden="true" className="hidden text-accent-bright sm:block">→</span>
          <CastRole label="Juge" detail="évalue les décisions" />
        </div>

        <Switch
          label="Activer le dialogue multi-modèle"
          desc={
            campaign
              ? "Conserver les règles et l’histoire du chapitre, mais comparer plusieurs familles d’IA à la même table."
              : "Comparer plusieurs styles de négociation dans une partie classique sans changer la boucle de jeu."
          }
          checked={enabled}
          disabled={models.length < 2}
          onChange={onEnabled}
        />
        {models.length < 2 && (
          <p className="mt-2 text-xs text-fg-faint">
            Le mode mono-modèle reste disponible. Installez un second modèle depuis le Laboratoire pour activer le dialogue multi-IA.
          </p>
        )}
        {enabled && (
          <div className="mt-4 space-y-3 border-t border-edge pt-4">
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
              {models.map((model) => {
                const checked = selected.includes(model.tag);
                const blocked = !checked && selected.length >= 4;
                return (
                  <label
                    key={model.tag}
                    className={`flex cursor-pointer gap-2 rounded-lg border p-3 transition-colors ${
                      checked ? "border-accent bg-accent/10" : "border-edge bg-surface-2/30"
                    } ${blocked ? "cursor-not-allowed opacity-45" : "hover:border-edge-strong"}`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={blocked}
                      onChange={() => toggle(model.tag)}
                      className="mt-0.5 accent-indigo-400"
                    />
                    <span className="min-w-0">
                      <span className="block truncate text-xs font-semibold">{model.family}</span>
                      <span className="block truncate font-mono text-[10px] text-fg-faint">
                        {model.tag} · {model.expected_size_gb} Go
                      </span>
                      {model.benchmark_status === "schema_valid" && (
                        <span className="block text-[10px] text-good">
                          {model.benchmark_tokens_per_second.toFixed(1)} tok/s local
                        </span>
                      )}
                    </span>
                  </label>
                );
              })}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-fg-muted">
              <span>{selected.length}/4 modèles · affectation par pays à l’étape suivante</span>
              <span className="text-warn">Exécution séquentielle sur un seul GPU</span>
            </div>
            {selected.length >= 1 && (
              <p className="text-[11px] text-fg-faint">
                Game Master : <span className="font-mono text-foreground">{selected[0]}</span> · juge :{" "}
                <span className="font-mono text-foreground">{selected[selected.length - 1]}</span>
              </p>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}

export function CountryModelAssignments({
  countries,
  humanCountry,
  selectedModels,
  assignments,
  onAssignments,
  compact = false,
}: {
  countries: string[];
  humanCountry?: string | null;
  selectedModels: string[];
  assignments: Record<string, string>;
  onAssignments: (assignments: Record<string, string>) => void;
  compact?: boolean;
}) {
  const aiCountries = [...new Set(countries)]
    .filter((country) => country !== humanCountry)
    .sort();
  const effective = completeCountryAssignments(
    aiCountries,
    selectedModels,
    assignments,
    humanCountry,
  );

  return (
    <div data-tour="model-assignments">
    <Panel className="border-accent/35 bg-accent/5">
      <PanelTitle
        kicker="Casting explicite"
        title="Quelle IA incarne quel pays ?"
        hint="Cette affectation est figée dans la sauvegarde et pilote réellement le moteur. Un même modèle peut incarner plusieurs pays."
        right={
          <button
            type="button"
            onClick={() =>
              onAssignments(
                completeCountryAssignments(aiCountries, selectedModels, {}, humanCountry),
              )
            }
            disabled={selectedModels.length < 1}
            className="rounded-md border border-edge px-2.5 py-1.5 text-xs text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground disabled:opacity-40"
          >
            Répartir automatiquement
          </button>
        }
      />
      {humanCountry && (
        <p className="mb-3 text-xs text-fg-faint">
          {speakerMeta(humanCountry).label} est joué par l’humain et n’a donc pas de modèle.
        </p>
      )}
      <div className={`grid gap-2 ${compact ? "md:grid-cols-2" : "md:grid-cols-2 xl:grid-cols-3"}`}>
        {aiCountries.map((country) => (
          <label
            key={country}
            className="flex items-center gap-3 rounded-lg border border-edge bg-background/45 p-3"
          >
            <SpeakerAvatar id={country} size={28} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-semibold">
                {speakerMeta(country).label}
              </span>
              <span className="text-[10px] uppercase tracking-wide text-fg-faint">délégation IA</span>
            </span>
            <select
              aria-label={`Modèle de ${speakerMeta(country).label}`}
              value={effective[country] ?? ""}
              disabled={selectedModels.length < 1}
              onChange={(event) =>
                onAssignments({ ...effective, [country]: event.target.value })
              }
              className="max-w-[12rem] rounded-md border border-edge bg-surface-2 px-2 py-1.5 font-mono text-[11px] outline-none focus:border-accent-bright"
            >
              {selectedModels.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      {!aiCountries.length && (
        <p className="text-xs text-fg-faint">Sélectionne d’abord les pays de la table.</p>
      )}
    </Panel>
    </div>
  );
}

function CastRole({ label, detail }: { label: string; detail: string }) {
  return (
    <div className="rounded-md border border-edge bg-background/35 px-3 py-2">
      <p className="text-xs font-semibold text-foreground">{label}</p>
      <p className="mt-0.5 text-[10px] text-fg-faint">{detail}</p>
    </div>
  );
}
