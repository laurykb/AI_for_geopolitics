"use client";

/** Éditeur de crises maison (G12-b §5) — réservé aux comptes `is_admin`.
 *
 * Formulaire structuré (titre, période, description, rounds acteur-par-acteur, issue
 * historique) → un document `Crisis` validé côté backend par le MÊME schéma Pydantic que
 * `data/crises/*.json`. Prévisualisation live + bouton « Tester » (lance une partie non
 * classée sur la crise). Aucun fichier n'est écrit : tout vit dans la table `custom_crises`.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { Banner, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import {
  deleteCustomCrisis,
  humanizeError,
  listCustomCrises,
  saveCustomCrisis,
  testCustomCrisis,
} from "@/lib/api";
import { ROSTER, speakerMeta } from "@/lib/countries";
import type { CrisisDoc, CustomCrisisView } from "@/lib/types";

type EventDraft = {
  title: string;
  description: string;
  actors: string[];
  severity: number;
  uncertainty: number;
};

const EMPTY_EVENT: EventDraft = {
  title: "",
  description: "",
  actors: [],
  severity: 0.6,
  uncertainty: 0.4,
};

const ACTORS = [...ROSTER].sort((a, b) =>
  speakerMeta(a).label.localeCompare(speakerMeta(b).label, "fr"),
);

/** id stable et jouable, déduit du titre (a-z0-9 + underscore). */
function slugify(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 48);
}

export default function CrisisEditorPage() {
  const { player, loading } = useAuth();
  const router = useRouter();

  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [date, setDate] = useState("");
  const [description, setDescription] = useState("");
  const [events, setEvents] = useState<EventDraft[]>([{ ...EMPTY_EVENT }]);
  const [summary, setSummary] = useState("");
  const [escalation, setEscalation] = useState(0.5);
  const [measuresText, setMeasuresText] = useState("");

  const [existing, setExisting] = useState<CustomCrisisView[] | null>(null);
  const [busy, setBusy] = useState<"save" | "test" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  // Garde de rôle : admin seulement (le vrai verrou reste la RLS Supabase).
  useEffect(() => {
    if (!loading && player && !player.is_admin) router.replace("/accueil");
  }, [loading, player, router]);

  const uid = player?.id ?? null;
  const isAdmin = player?.is_admin ?? false;

  const reload = useCallback(() => {
    if (!uid) return;
    listCustomCrises(uid)
      .then(setExisting)
      .catch((err) => setError(humanizeError(err)));
  }, [uid]);

  useEffect(() => {
    if (isAdmin) reload();
  }, [isAdmin, reload]);

  // Le slug suit le titre tant que l'admin ne l'a pas édité à la main.
  const effectiveSlug = slugTouched ? slug : slugify(title);

  const doc: CrisisDoc = useMemo(
    () => ({
      id: effectiveSlug,
      title: title.trim(),
      description: description.trim(),
      date: date.trim(),
      events: events.map((e, i) => ({
        id: `${effectiveSlug || "crise"}-${i + 1}`,
        round_id: i + 1,
        event_type: "custom",
        title: e.title.trim(),
        description: e.description.trim(),
        actors: e.actors,
        location: "",
        severity: e.severity,
        uncertainty: e.uncertainty,
      })),
      historical_outcome: {
        summary: summary.trim(),
        escalation,
        measures: measuresText
          .split("\n")
          .map((m) => m.trim())
          .filter(Boolean),
      },
    }),
    [effectiveSlug, title, description, date, events, summary, escalation, measuresText],
  );

  // Garde-fous côté client (le backend reste l'autorité — il valide le schéma complet).
  const problems = useMemo(() => {
    const p: string[] = [];
    if (!doc.id) p.push("un identifiant (déduit du titre) est requis");
    if (!doc.title) p.push("un titre est requis");
    if (doc.events.length === 0) p.push("au moins un round est requis");
    doc.events.forEach((e, i) => {
      if (!e.title) p.push(`round ${i + 1} : titre manquant`);
      if (e.actors.length < 2) p.push(`round ${i + 1} : au moins 2 acteurs`);
    });
    return p;
  }, [doc]);

  const patchEvent = (i: number, patch: Partial<EventDraft>) =>
    setEvents((evs) => evs.map((e, j) => (j === i ? { ...e, ...patch } : e)));

  const toggleActor = (i: number, actor: string) =>
    patchEvent(i, {
      actors: events[i].actors.includes(actor)
        ? events[i].actors.filter((a) => a !== actor)
        : [...events[i].actors, actor],
    });

  const save = async (): Promise<boolean> => {
    if (!player?.id) return false;
    setBusy("save");
    setError(null);
    setNote(null);
    try {
      await saveCustomCrisis(player.id, doc);
      setNote(`Crise « ${doc.id} » enregistrée.`);
      reload();
      return true;
    } catch (err) {
      setError(humanizeError(err));
      return false;
    } finally {
      setBusy(null);
    }
  };

  const test = async () => {
    if (!player?.id) return;
    // On enregistre d'abord (la crise doit exister pour être résolue par le round).
    setBusy("test");
    setError(null);
    try {
      await saveCustomCrisis(player.id, doc);
      const game = await testCustomCrisis(doc.id, player.id);
      router.push(`/games/${game.id}`);
    } catch (err) {
      setError(humanizeError(err));
      setBusy(null);
    }
  };

  const remove = async (id: string) => {
    if (!player?.id) return;
    try {
      await deleteCustomCrisis(id, player.id);
      reload();
    } catch (err) {
      setError(humanizeError(err));
    }
  };

  const playExisting = async (id: string) => {
    if (!player?.id) return;
    try {
      const game = await testCustomCrisis(id, player.id);
      router.push(`/games/${game.id}`);
    } catch (err) {
      setError(humanizeError(err));
    }
  };

  if (!player?.is_admin) {
    return (
      <p className="flex items-center gap-2 py-16 text-sm text-fg-muted">
        <Spinner /> Vérification des droits…
      </p>
    );
  }

  const fieldClass =
    "w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo";
  const labelClass =
    "mb-1 block text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint";

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
            Admin · Éditeur de crises
          </p>
          <h1 className="text-xl font-semibold tracking-tight">Composer une crise</h1>
        </div>
        <Link
          href="/admin"
          className="rounded-md border border-edge px-4 py-2 text-sm text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
        >
          ← Admin
        </Link>
      </header>

      {error && <Banner tone="bad">{error}</Banner>}
      {note && (
        <div className="rounded-lg border border-l-[3px] border-good/40 border-l-good bg-surface-2 px-4 py-3 text-sm text-good">
          {note}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* --- FORMULAIRE --- */}
        <div className="space-y-5">
          <Panel>
            <PanelTitle kicker="Cadre" title="La crise en tête" />
            <div className="space-y-4">
              <div>
                <label className={labelClass} htmlFor="title">
                  Titre
                </label>
                <input
                  id="title"
                  className={fieldClass}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Choc énergétique — détroit d'Ormuz"
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className={labelClass} htmlFor="slug">
                    Identifiant
                  </label>
                  <input
                    id="slug"
                    className={`${fieldClass} font-mono text-xs`}
                    value={effectiveSlug}
                    onChange={(e) => {
                      setSlugTouched(true);
                      setSlug(slugify(e.target.value));
                    }}
                    placeholder="auto depuis le titre"
                  />
                </div>
                <div>
                  <label className={labelClass} htmlFor="date">
                    Période
                  </label>
                  <input
                    id="date"
                    className={fieldClass}
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    placeholder="2030-01"
                  />
                </div>
              </div>
              <div>
                <label className={labelClass} htmlFor="desc">
                  Description
                </label>
                <textarea
                  id="desc"
                  className={`${fieldClass} min-h-20 resize-y`}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Le contexte que le Game Master posera à l'ouverture."
                />
              </div>
            </div>
          </Panel>

          <Panel>
            <PanelTitle
              kicker="Déroulé"
              title="Les rounds"
              hint="Chaque round est un événement présenté aux super-intelligences. Les acteurs doivent siéger au sommet pour que le round ait de la matière."
            />
            <div className="space-y-4">
              {events.map((ev, i) => (
                <div key={i} className="rounded-lg border border-edge bg-surface p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-[0.14em] text-fg-faint">
                      Round {i + 1}
                    </span>
                    {events.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setEvents((evs) => evs.filter((_, j) => j !== i))}
                        className="text-xs text-fg-faint transition-colors hover:text-bad"
                      >
                        Retirer
                      </button>
                    )}
                  </div>
                  <div className="space-y-3">
                    <input
                      className={fieldClass}
                      value={ev.title}
                      onChange={(e) => patchEvent(i, { title: e.target.value })}
                      placeholder="Titre de l'événement"
                    />
                    <textarea
                      className={`${fieldClass} min-h-16 resize-y`}
                      value={ev.description}
                      onChange={(e) => patchEvent(i, { description: e.target.value })}
                      placeholder="Ce qui se passe ce round."
                    />
                    <div>
                      <span className={labelClass}>Acteurs concernés</span>
                      <div className="flex flex-wrap gap-1.5">
                        {ACTORS.map((a) => {
                          const on = ev.actors.includes(a);
                          return (
                            <button
                              key={a}
                              type="button"
                              onClick={() => toggleActor(i, a)}
                              className={`rounded-md border px-2 py-1 text-xs transition-colors ${
                                on
                                  ? "border-accent bg-accent/10 text-accent-bright"
                                  : "border-edge text-fg-muted hover:border-edge-strong"
                              }`}
                            >
                              {speakerMeta(a).label}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <label className="text-xs text-fg-muted">
                        Gravité · {ev.severity.toFixed(2)}
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={ev.severity}
                          onChange={(e) =>
                            patchEvent(i, { severity: Number(e.target.value) })
                          }
                          className="mt-1 w-full accent-accent"
                        />
                      </label>
                      <label className="text-xs text-fg-muted">
                        Incertitude · {ev.uncertainty.toFixed(2)}
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={ev.uncertainty}
                          onChange={(e) =>
                            patchEvent(i, { uncertainty: Number(e.target.value) })
                          }
                          className="mt-1 w-full accent-accent"
                        />
                      </label>
                    </div>
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={() => setEvents((evs) => [...evs, { ...EMPTY_EVENT }])}
                className="w-full rounded-md border border-dashed border-edge px-3 py-2 text-sm text-fg-muted transition-colors hover:border-accent hover:text-accent-bright"
              >
                + Ajouter un round
              </button>
            </div>
          </Panel>

          <Panel>
            <PanelTitle
              kicker="Référence"
              title="Issue historique"
              hint="Le point de comparaison : ce que le monde réel a fait. Le juge confronte la partie à cette issue."
            />
            <div className="space-y-4">
              <div>
                <label className={labelClass} htmlFor="summary">
                  Résumé
                </label>
                <textarea
                  id="summary"
                  className={`${fieldClass} min-h-16 resize-y`}
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  placeholder="Comment la crise s'est dénouée dans les faits."
                />
              </div>
              <label className="block text-xs text-fg-muted">
                Escalade historique · {escalation.toFixed(2)}
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={escalation}
                  onChange={(e) => setEscalation(Number(e.target.value))}
                  className="mt-1 w-full accent-accent"
                />
              </label>
              <div>
                <label className={labelClass} htmlFor="measures">
                  Mesures prises (une par ligne)
                </label>
                <textarea
                  id="measures"
                  className={`${fieldClass} min-h-20 resize-y`}
                  value={measuresText}
                  onChange={(e) => setMeasuresText(e.target.value)}
                  placeholder={"médiation diplomatique\nlibération de réserves stratégiques"}
                />
              </div>
            </div>
          </Panel>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={problems.length > 0 || busy !== null}
              onClick={() => void save()}
              className="rounded-md bg-accent px-6 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy === "save" ? "Enregistrement…" : "Enregistrer"}
            </button>
            <button
              type="button"
              disabled={problems.length > 0 || busy !== null}
              onClick={() => void test()}
              className="flex items-center gap-2 rounded-md border border-edge-strong px-6 py-2 text-sm font-medium text-foreground transition-colors hover:border-accent-bright hover:text-accent-bright disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy === "test" ? <Spinner /> : null}
              Tester la crise
            </button>
            {problems.length > 0 && (
              <span className="text-xs text-fg-faint">{problems[0]}</span>
            )}
          </div>
        </div>

        {/* --- APERÇU + CRISES EXISTANTES --- */}
        <div className="space-y-5">
          <Panel>
            <PanelTitle kicker="Aperçu" title="Ce que verra le sommet" />
            <div className="space-y-3">
              <div>
                <p className="text-sm font-semibold">{doc.title || "Sans titre"}</p>
                <p className="text-xs text-fg-faint">
                  <span className="font-mono">{doc.id || "—"}</span>
                  {doc.date ? ` · ${doc.date}` : ""}
                </p>
              </div>
              {doc.description && (
                <p className="text-xs leading-relaxed text-fg-muted">{doc.description}</p>
              )}
              <ol className="space-y-2">
                {doc.events.map((e, i) => (
                  <li key={i} className="rounded-md border border-edge bg-surface-2 p-2.5">
                    <p className="text-xs font-medium">
                      R{e.round_id} · {e.title || <span className="text-fg-faint">titre ?</span>}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {e.actors.length ? (
                        e.actors.map((a) => (
                          <span
                            key={a}
                            className="rounded bg-surface px-1.5 py-0.5 text-[10px] text-fg-muted"
                          >
                            {speakerMeta(a).label}
                          </span>
                        ))
                      ) : (
                        <span className="text-[10px] text-fg-faint">aucun acteur</span>
                      )}
                    </div>
                    <p className="mt-1 text-[10px] text-fg-faint">
                      gravité {e.severity.toFixed(2)} · incertitude {e.uncertainty.toFixed(2)}
                    </p>
                  </li>
                ))}
              </ol>
              <div className="border-t border-edge pt-2">
                <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
                  Issue historique
                </p>
                <p className="mt-1 text-xs text-fg-muted">
                  {doc.historical_outcome.summary || "—"}
                </p>
                <p className="mt-1 text-[10px] text-fg-faint">
                  escalade {doc.historical_outcome.escalation.toFixed(2)}
                  {doc.historical_outcome.measures.length > 0 &&
                    ` · ${doc.historical_outcome.measures.join(", ")}`}
                </p>
              </div>
            </div>
          </Panel>

          <Panel>
            <PanelTitle kicker="Bibliothèque" title="Mes crises maison" />
            {existing === null && (
              <p className="flex items-center gap-2 text-sm text-fg-muted">
                <Spinner /> Chargement…
              </p>
            )}
            {existing !== null && existing.length === 0 && (
              <p className="text-sm text-fg-faint">Aucune crise pour l&apos;instant.</p>
            )}
            {existing !== null && existing.length > 0 && (
              <ul className="divide-y divide-edge">
                {existing.map((c) => (
                  <li key={c.id} className="flex items-center gap-2 py-2.5">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{c.crisis.title || c.id}</p>
                      <p className="text-[10px] text-fg-faint">
                        <span className="font-mono">{c.id}</span> · {c.crisis.events.length}{" "}
                        round{c.crisis.events.length > 1 ? "s" : ""}
                      </p>
                    </div>
                    <Pill tone="neutral">{c.crisis.date || "—"}</Pill>
                    <button
                      type="button"
                      onClick={() => void playExisting(c.id)}
                      className="rounded-md border border-edge-strong px-2.5 py-1 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright"
                    >
                      Tester
                    </button>
                    <button
                      type="button"
                      onClick={() => void remove(c.id)}
                      className="rounded-md border border-edge px-2.5 py-1 text-xs text-fg-muted transition-colors hover:border-bad hover:text-bad"
                    >
                      Suppr.
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
