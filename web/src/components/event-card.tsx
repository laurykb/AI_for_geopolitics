/** Carte de l'événement du round (posé par le Game Master ou décrété par l'humain). */

import { speakerMeta } from "@/lib/countries";
import type { GeoEvent } from "@/lib/types";

import { SpeakerAvatar } from "./avatar";
import { Meter, Panel, PanelTitle, Pill } from "./ui";

export function EventCard({ event, date }: { event: GeoEvent; date?: string }) {
  const when = event.date || date;
  return (
    <Panel className="border-l-2 border-l-accent">
      <PanelTitle
        kicker="Événement du round"
        title={event.title}
        right={
          <Pill tone="accent">
            {event.event_type === "human" ? "décrété par l'humain" : event.event_type}
          </Pill>
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
            label="Gravité"
            value={event.severity ?? 0.5}
            hint="Poids de l'événement selon le Game Master (0 = anodin, 1 = majeur)."
          />
          <Meter
            label="Incertitude"
            value={event.uncertainty ?? 0.5}
            hint="Part de brouillard : à quel point les faits sont-ils établis ?"
          />
        </span>
      </div>
    </Panel>
  );
}
