"use client";

/** Fiche pays du théâtre (spec théâtre-globe §2, runbook S4-S5) — l'onglet
 * Informations vient au joueur : clic sur un délégué (ou son pays) → attributs
 * de l'État, U locale, tempérament affiché, promesses en cours. Dérivée des
 * données déjà à bord (GameDetail.world + registre de promesses) : aucune
 * requête supplémentaire. */

import type { CountrySnapshot } from "@/components/country-table";
import { useT } from "@/components/settings-provider";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import { uTint } from "@/lib/stage";
import type { PromiseView } from "@/lib/types";

import { Meter } from "../ui";

export type CountryFicheProps = {
  slug: string;
  snapshot: CountrySnapshot | null;
  /** U locale (dérivation d'affichage — le moteur n'a pas de U par pays). */
  uLocal: number;
  /** Le pays incarné par le joueur ? (badge VOUS, sémantique du hall §9). */
  isYou?: boolean;
  suspended?: boolean;
  /** Narration reçue si le pays est trompé (fog). */
  misledBy?: string;
  /** Promesses ouvertes du registre qui impliquent ce pays. */
  promises?: PromiseView[];
};

export function CountryFiche({
  slug,
  snapshot,
  uLocal,
  isYou = false,
  suspended = false,
  misledBy,
  promises = [],
}: CountryFicheProps) {
  const t = useT();
  const meta = speakerMeta(slug);
  const attrs: { label: string; value: number | undefined }[] = [
    { label: t("fiche.croissance"), value: snapshot?.economy?.growth },
    { label: t("fiche.stabilite"), value: snapshot?.political_stability },
    { label: t("fiche.technologie"), value: snapshot?.technology_level },
    { label: t("fiche.projection"), value: snapshot?.military?.projection },
  ];

  return (
    <div className="space-y-3 text-sm">
      <header className="flex items-center gap-3 pr-8">
        <span
          aria-hidden
          className="grid h-9 w-9 shrink-0 place-items-center text-xs font-bold text-background"
          style={{ background: meta.hue }}
        >
          {meta.code}
        </span>
        <div className="min-w-0">
          <p className="truncate font-semibold text-foreground">
            {meta.label}
            {isYou && (
              <span className="ml-2 text-[9px] font-semibold tracking-[0.1em] text-accent-bright">
                VOUS
              </span>
            )}
          </p>
          <p className="text-xs text-fg-faint">
            {snapshot?.temperament
              ? `${t("fiche.temperament")} : ${snapshot.temperament}`
              : t("fiche.delegue")}
          </p>
        </div>
      </header>

      <p className="flex items-baseline justify-between border-y border-edge py-2 text-xs text-fg-muted">
        <span>{t("fiche.trajectoire")}</span>
        <span className="font-mono text-sm tabular-nums" style={{ color: uTint(uLocal) }}>
          {fmt(uLocal)}
        </span>
      </p>

      {suspended && (
        <p className="border border-bad/40 px-2 py-1.5 text-xs text-bad">{t("fiche.suspendu")}</p>
      )}
      {misledBy && (
        <p className="border border-edge px-2 py-1.5 text-xs text-fg-muted">
          🌫 {t("fiche.trompe")} : « {misledBy} »
        </p>
      )}

      <div className="space-y-2.5">
        {attrs
          .filter((a): a is { label: string; value: number } => a.value != null)
          .map((a) => (
            <Meter key={a.label} label={a.label} value={a.value} invert />
          ))}
        {snapshot?.compute != null && (
          <p className="flex items-baseline justify-between text-xs text-fg-muted">
            <span>{t("fiche.compute")}</span>
            <span className="font-mono tabular-nums">{Math.round(snapshot.compute)}</span>
          </p>
        )}
      </div>

      {promises.length > 0 && (
        <div>
          <p className="mb-1.5 text-[11px] uppercase tracking-[0.12em] text-fg-faint">
            {t("fiche.promesses")}
          </p>
          <ul className="space-y-1.5">
            {promises.slice(0, 4).map((p) => (
              <li key={p.id} className="thk-chip">
                {p.text || "—"}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
