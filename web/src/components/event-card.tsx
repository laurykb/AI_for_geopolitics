"use client";

/** Carte de l'événement du round (posé par le Game Master ou décrété par l'humain). */

import { speakerMeta } from "@/lib/countries";
import type { GeoEvent } from "@/lib/types";

import { SpeakerAvatar } from "./avatar";
import { useT } from "./settings-provider";
import { Meter, Panel, PanelTitle, Pill } from "./ui";

export function EventCard({
  event,
  date,
  truth = false,
}: {
  event: GeoEvent;
  date?: string;
  truth?: boolean; // boîte de verre (Fog) : cet événement est la vérité, que toi seul vois
}) {
  const t = useT();
  const when = event.date || date;
  return (
    <Panel className="border-l-2 border-l-accent">
      <PanelTitle
        kicker={t("event.kicker")}
        title={event.title}
        right={
          <span className="flex items-center gap-2">
            {truth && <Pill tone="good">{t("event.verite")}</Pill>}
            <Pill tone={event.event_type === "motion" ? "warn" : "accent"}>
              {event.event_type === "human"
                ? t("event.type.humain")
                : event.event_type === "motion"
                  ? t("event.type.motion")
                  : // jamais le slug technique brut — libellé générique (audit n°3)
                    t("event.type.defaut")}
            </Pill>
          </span>
        }
      />
      {event.description && (
        <p className="mb-4 text-sm leading-relaxed text-fg-muted">{event.description}</p>
      )}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-xs text-fg-faint">
        {when && <span>{when}</span>}
        {event.location && <span>{event.location}</span>}
        {(event.actors?.length ?? 0) > 0 && (
          <span className="flex items-center gap-1.5">
            {event.actors!.map((a) => (
              <span key={a} title={speakerMeta(a).label}>
                <SpeakerAvatar id={a} size={22} />
              </span>
            ))}
          </span>
        )}
        <span className="ml-auto grid w-56 grid-cols-2 gap-3">
          <Meter
            label={t("event.gravite")}
            value={event.severity ?? 0.5}
            hint={t("event.gravite-aide")}
          />
          <Meter
            label={t("event.incertitude")}
            value={event.uncertainty ?? 0.5}
            hint={t("event.incertitude-aide")}
          />
        </span>
      </div>
    </Panel>
  );
}
