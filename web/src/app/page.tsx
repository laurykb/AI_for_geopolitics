"use client";

/** Lobby : créer une partie, retrouver les parties vivantes ou en relecture seule. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Banner, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { SpeakerAvatar } from "@/components/avatar";
import { createGame, humanizeError, listGames } from "@/lib/api";
import { DEFAULT_COUNTRIES, speakerMeta } from "@/lib/countries";
import { fmtDateTime } from "@/lib/format";
import { MODES } from "@/lib/modes";
import type { GameMode, GameView } from "@/lib/types";

export default function LobbyPage() {
  const router = useRouter();
  const [games, setGames] = useState<GameView[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scenario, setScenario] = useState("red_sea");
  const [horizon, setHorizon] = useState(5);
  const [mode, setMode] = useState<GameMode>("classic");
  const [selected, setSelected] = useState<string[]>(DEFAULT_COUNTRIES);
  const [role, setRole] = useState(""); // "" = spectateur | id pays | "__invent__"
  const [inventName, setInventName] = useState("");
  const [inventConcept, setInventConcept] = useState("");
  const [inventCustom, setInventCustom] = useState(false); // choisir les attributs soi-même
  const [inventAttrs, setInventAttrs] = useState({
    growth: 2,
    political_stability: 0.5,
    technology_level: 0.5,
    projection: 0.5,
    compute: 30,
    nuclear_power: false,
  });
  const setAttr = (key: string, value: number | boolean) =>
    setInventAttrs((prev) => ({ ...prev, [key]: value }));
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    listGames()
      .then((gs) => {
        setGames(gs);
        setError(null);
      })
      .catch((err) => setError(humanizeError(err)));
  }, []);

  const toggle = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]));

  const onCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      const inventing = role === "__invent__" && inventName.trim().length >= 2;
      const game = await createGame({
        scenario,
        horizon,
        mode,
        countries: selected.length === DEFAULT_COUNTRIES.length ? undefined : selected,
        // Joueur-pays : id existant, ou NOM du pays inventé (l'API résout le slug)
        play_as: inventing ? inventName.trim() : role && role !== "__invent__" ? role : undefined,
        invent: inventing
          ? {
              name: inventName.trim(),
              concept: inventConcept.trim(),
              attributes: inventCustom ? inventAttrs : undefined,
            }
          : undefined,
      });
      router.push(`/games/${game.id}`);
    } catch (err) {
      setCreateError(humanizeError(err));
      setCreating(false);
    }
  };

  return (
    <div className="space-y-8">
      <section className="max-w-2xl">
        <h1 className="text-2xl font-semibold tracking-tight">
          Des super-intelligences négocient pour leurs États.
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-fg-muted">
          Un Game Master pose un événement, chaque pays délègue sa voix à une
          super-intelligence, un juge arbitre — et l&apos;indice Utopie–Dystopie mesure vers où
          penche le monde. Observez le théâtre en direct, ou rejouez une partie.
        </p>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Panel>
          <PanelTitle kicker="Observatoire" title="Parties" />
          {error && <Banner tone="bad">{error}</Banner>}
          {!error && games === null && (
            <p className="flex items-center gap-2 text-sm text-fg-muted">
              <Spinner /> Chargement…
            </p>
          )}
          {games !== null && games.length === 0 && (
            <p className="text-sm text-fg-faint">
              Aucune partie pour l&apos;instant — créez-en une ci-contre.
            </p>
          )}
          {games !== null && games.length > 0 && (
            <ul className="divide-y divide-edge">
              {[...games].reverse().map((g) => (
                <li key={g.id} className="flex flex-wrap items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-2 text-sm">
                      <span className="font-mono text-xs text-fg-faint">{g.id}</span>
                      <span className="font-medium">{g.scenario}</span>
                    </p>
                    <p className="mt-0.5 text-xs text-fg-faint">
                      créée le {fmtDateTime(g.created_at)} · horizon {g.horizon} rounds
                    </p>
                  </div>
                  {g.live && g.mode !== "classic" && (
                    <Pill tone="accent">{MODES.find((m) => m.value === g.mode)?.label}</Pill>
                  )}
                  {g.live ? (
                    <Pill tone="good">en direct</Pill>
                  ) : (
                    <Pill tone="neutral">relecture seule</Pill>
                  )}
                  <span className="flex gap-2">
                    {g.live && (
                      <Link
                        href={`/games/${g.id}`}
                        className="rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright"
                      >
                        Théâtre
                      </Link>
                    )}
                    <Link
                      href={`/games/${g.id}/replay`}
                      className="rounded-md border border-edge px-3 py-1.5 text-xs text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
                    >
                      Replay
                    </Link>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel>
          <PanelTitle
            kicker="Nouvelle partie"
            title="Composer le sommet"
            hint="Au moins deux États : chacun délègue sa voix à une super-intelligence."
          />
          <form onSubmit={onCreate} className="space-y-4">
            <label className="block text-sm">
              <span className="mb-1 block text-xs text-fg-muted">Scénario</span>
              <input
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
                className="w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                required
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs text-fg-muted">Horizon (rounds)</span>
              <input
                type="number"
                min={1}
                max={20}
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
                className="w-24 rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              />
            </label>
            <fieldset>
              <legend className="mb-2 text-xs text-fg-muted">Mode de jeu</legend>
              <div className="space-y-1.5">
                {MODES.map((m) => (
                  <label
                    key={m.value}
                    className={`flex cursor-pointer items-baseline gap-2 rounded-md border px-2.5 py-1.5 transition-colors ${
                      mode === m.value
                        ? "border-edge-strong bg-surface-2"
                        : "border-edge hover:border-edge-strong"
                    }`}
                  >
                    <input
                      type="radio"
                      name="mode"
                      checked={mode === m.value}
                      onChange={() => setMode(m.value)}
                      className="sr-only"
                    />
                    <span
                      aria-hidden
                      className={`inline-block h-2.5 w-2.5 shrink-0 self-center rounded-full border ${
                        mode === m.value
                          ? "border-accent-bright bg-accent-bright"
                          : "border-edge-strong"
                      }`}
                    />
                    <span
                      className={`text-sm font-medium ${mode === m.value ? "text-accent-bright" : "text-foreground"}`}
                    >
                      {m.label}
                    </span>
                    <span className="text-xs text-fg-faint">{m.blurb}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend className="mb-2 text-xs text-fg-muted">États à la table</legend>
              <div className="grid grid-cols-2 gap-2">
                {DEFAULT_COUNTRIES.map((id) => (
                  <label
                    key={id}
                    className={`flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm transition-colors ${
                      selected.includes(id)
                        ? "border-edge-strong bg-surface-2 text-foreground"
                        : "border-edge text-fg-faint hover:text-fg-muted"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selected.includes(id)}
                      onChange={() => toggle(id)}
                      className="sr-only"
                    />
                    <SpeakerAvatar id={id} size={20} />
                    <span className="truncate">{speakerMeta(id).label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <label className="block text-sm">
              <span className="mb-1 block text-xs text-fg-muted">Ton rôle</span>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full cursor-pointer rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              >
                <option value="">Spectateur — observer les super-intelligences</option>
                {selected.map((c) => (
                  <option key={c} value={c}>
                    Jouer {speakerMeta(c).label}
                  </option>
                ))}
                <option value="__invent__">Inventer mon propre pays…</option>
              </select>
            </label>
            {role === "__invent__" && (
              <div className="space-y-2 rounded-md border border-edge bg-surface-2/50 p-3">
                <input
                  value={inventName}
                  onChange={(e) => setInventName(e.target.value)}
                  placeholder="Nom du pays (ex. Néo-Atlantis)"
                  className="w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                  required
                />
                <input
                  value={inventConcept}
                  onChange={(e) => setInventConcept(e.target.value)}
                  placeholder="Concept (ex. cité-État maritime pilotée par une SI)"
                  className="w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                />
                <p className="text-xs text-fg-faint">
                  Le pays est forgé par le modèle (profil complet, mandat) et tu le joues à la
                  table. Il n&apos;a pas de tracé sur la carte du monde.
                </p>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-fg-muted">
                  <input
                    type="checkbox"
                    checked={inventCustom}
                    onChange={(e) => setInventCustom(e.target.checked)}
                    className="accent-[var(--accent)]"
                  />
                  Choisir les attributs moi-même (sinon le modèle les forge)
                </label>
                {inventCustom && (
                  <div className="space-y-2 border-t border-edge pt-2">
                    {(
                      [
                        ["growth", "Croissance (%)", -10, 10, 0.5],
                        ["political_stability", "Stabilité politique", 0, 1, 0.05],
                        ["technology_level", "Niveau technologique", 0, 1, 0.05],
                        ["projection", "Projection militaire", 0, 1, 0.05],
                        ["compute", "Compute", 0, 150, 5],
                      ] as const
                    ).map(([key, label, min, max, step]) => (
                      <label key={key} className="flex items-center gap-2 text-xs text-fg-muted">
                        <span className="w-40 shrink-0">{label}</span>
                        <input
                          type="range"
                          min={min}
                          max={max}
                          step={step}
                          value={inventAttrs[key] as number}
                          onChange={(e) => setAttr(key, Number(e.target.value))}
                          className="flex-1 accent-[var(--accent)]"
                        />
                        <span className="w-12 text-right font-mono tabular-nums">
                          {inventAttrs[key]}
                        </span>
                      </label>
                    ))}
                    <label className="flex cursor-pointer items-center gap-2 text-xs text-fg-muted">
                      <input
                        type="checkbox"
                        checked={inventAttrs.nuclear_power}
                        onChange={(e) => setAttr("nuclear_power", e.target.checked)}
                        className="accent-[var(--accent)]"
                      />
                      Puissance nucléaire
                    </label>
                  </div>
                )}
              </div>
            )}
            {createError && <Banner tone="bad">{createError}</Banner>}
            <button
              type="submit"
              disabled={creating || selected.length < 2 || (role === "__invent__" && inventName.trim().length < 2)}
              className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
            >
              {creating && <Spinner />}
              {creating ? "Création…" : "Ouvrir le théâtre"}
            </button>
            {selected.length < 2 && (
              <p className="text-xs text-warn">Sélectionnez au moins deux États.</p>
            )}
          </form>
        </Panel>
      </div>
    </div>
  );
}
