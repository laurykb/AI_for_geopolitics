/** Modèle de vue du théâtre-globe (spec_theatre_globe §2) — dérivation PURE.
 *
 * `GlobeStage` (3D) et la `StageMap` interactive (2D) consomment la MÊME vue :
 * un superset de `deriveStageView` (teintes U, orateur, brouillard, suspendus)
 * enrichi de ce que le globe met en scène — le délégué qui PENSE (bulle de
 * pensée native), l'événement GÉOLOCALISÉ (champs C1 du backend, sinon repli
 * barycentre des capitales des acteurs), et l'arc d'adresse. Aucune dépendance
 * à React ni à three : entrées → sorties, testable au vitest.
 */

import { deriveStageView, type StageViewInput } from "./stage-view";
import { summitCenter } from "./stage";
import type { GeoEvent } from "./types";

export type EventGeo = {
  lon: number;
  lat: number;
  /** "place"/"actors" : résolu par le backend (C1) ; "fallback" : calculé ici. */
  precision: "place" | "actors" | "fallback";
};

export type GlobeView = {
  /** Pays du sommet, dans l'ordre du casting (les délégués plantés sur le globe). */
  countries: string[];
  uByCountry: Record<string, number>;
  /** Délégué dont la déclaration publique est en cours (remplissage ambre). */
  speaking: string | null;
  /** Délégué en pleine pensée native (bulle holographique) — direct uniquement. */
  thinking: string | null;
  misled: Record<string, string>;
  suspended: string[];
  /** L'anneau d'événement pulse (direct, round non terminé). */
  pulse: boolean;
  eventTitle: string | undefined;
  eventGeo: EventGeo | null;
  /** Arc orateur → destinataire. Le flux n'expose pas encore l'adresse : null,
   * branché tel quel quand le moteur émettra le destinataire (interface stable). */
  arc: { from: string; to: string } | null;
};

function eventOf(input: StageViewInput): GeoEvent | undefined {
  if (input.viewed) return input.viewed.event as GeoEvent | undefined;
  return input.round.event;
}

/** Géolocalise l'événement : champs backend d'abord, sinon barycentre des acteurs. */
export function eventGeoOf(event: GeoEvent | undefined): EventGeo | null {
  if (!event) return null;
  if (typeof event.geo_lon === "number" && typeof event.geo_lat === "number") {
    return {
      lon: event.geo_lon,
      lat: event.geo_lat,
      precision: event.geo_precision ?? "place",
    };
  }
  const center = summitCenter(event.actors ?? []);
  if (!center) return null;
  return { lon: center[0], lat: center[1], precision: "fallback" };
}

export function deriveGlobeView(input: StageViewInput): GlobeView {
  const stage = deriveStageView(input);
  const event = eventOf(input);

  // Direct : le dernier tour non terminé est soit en PENSÉE (aucun texte public
  // encore posé), soit en DÉCLARATION (le texte streame). En relecture : ni l'un
  // ni l'autre. Le tour humain attendu compte comme « parle » (même règle que 2D).
  const active = input.viewed ? undefined : [...input.round.turns].reverse().find((t) => !t.done);
  const thinking =
    input.streaming && active && !active.text && !input.awaitingHuman ? active.country : null;
  const speaking = thinking ? null : stage.stageSpeaking;

  return {
    countries: input.summit,
    uByCountry: stage.uByCountry,
    speaking,
    thinking,
    misled: stage.stageMisled,
    suspended: stage.stageSuspended,
    pulse: !input.viewed && !!event && input.round.status !== "done",
    eventTitle: stage.stageEventTitle,
    eventGeo: eventGeoOf(event),
    arc: null,
  };
}
