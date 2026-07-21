"use client";

/** Atelier de développement du théâtre-globe (runbook S1-S2) — PAS une surface
 * du jeu : aucune navigation n'y mène, la page sert à itérer visuellement sur
 * `GlobeStage` avec l'app qui tourne, avant son branchement au théâtre (S3-S4).
 * Les boutons simulent les états du direct (pense, parle, événement, verdict,
 * suspension, brouillard, arc) à la main. */

import dynamic from "next/dynamic";
import { useState } from "react";

import { speakerMeta } from "@/lib/countries";

const GlobeStage = dynamic(
  () => import("@/components/globe/globe-stage").then((m) => m.GlobeStage),
  { ssr: false },
);

const SUMMIT = ["usa", "china", "iran", "france", "egypt", "saudi_arabia", "uk"];
const U_BY_COUNTRY: Record<string, number> = {
  usa: 0.58,
  china: 0.55,
  iran: 0.41,
  france: 0.61,
  egypt: 0.47,
  saudi_arabia: 0.5,
  uk: 0.57,
};
const ORMUZ = { lon: 56.5, lat: 26.6, precision: "place" as const };

export default function GlobeDevPage() {
  const [speakerIdx, setSpeakerIdx] = useState<number>(-1);
  const [phase, setPhase] = useState<"thinking" | "speaking">("speaking");
  const [picked, setPicked] = useState<string | null>(null);
  const [eventOn, setEventOn] = useState(false);
  const [frozen, setFrozen] = useState(false);
  const [suspendIran, setSuspendIran] = useState(false);
  const [fogEgypt, setFogEgypt] = useState(false);
  const [arcOn, setArcOn] = useState(false);
  const [view, setView] = useState<"3d" | "2d">("3d");

  const current = speakerIdx >= 0 ? SUMMIT[speakerIdx % SUMMIT.length] : null;
  const speaking = phase === "speaking" ? current : null;
  const thinking = phase === "thinking" ? current : null;

  const chip =
    "rounded border border-edge px-2 py-1 hover:bg-surface data-[on=true]:border-amber-400/60 data-[on=true]:text-amber-200";

  return (
    <main className="fixed inset-0 bg-[#04060c]">
      <GlobeStage
        countries={SUMMIT}
        uByCountry={U_BY_COUNTRY}
        utopia={0.52}
        speaking={speaking}
        thinking={thinking}
        misled={fogEgypt ? { egypt: "narratif brouillé (démo)" } : {}}
        suspended={suspendIran ? ["iran"] : []}
        eventTitle={eventOn ? "Incident naval dans le détroit d'Ormuz" : undefined}
        eventGeo={eventOn ? ORMUZ : null}
        pulse={eventOn}
        frozen={frozen}
        arc={arcOn ? { from: "usa", to: "iran" } : null}
        view={view}
        onViewToggle={() => setView((v) => (v === "3d" ? "2d" : "3d"))}
        onCountryClick={setPicked}
        className="h-full w-full"
      />
      <div className="absolute bottom-4 left-4 z-10 flex max-w-[92%] flex-wrap items-center gap-2 rounded-lg border border-edge bg-surface/85 px-3 py-2 text-xs text-foreground backdrop-blur">
        <button
          type="button"
          className={chip}
          onClick={() => {
            setPhase("thinking");
            setSpeakerIdx((i) => (phase === "thinking" ? i + 1 : Math.max(0, i)));
          }}
        >
          💭 pense
        </button>
        <button
          type="button"
          className={chip}
          onClick={() => {
            setPhase("speaking");
            setSpeakerIdx((i) => (phase === "speaking" ? i + 1 : Math.max(0, i)));
          }}
        >
          🗣 parle / suivant
        </button>
        <button type="button" className={chip} onClick={() => setSpeakerIdx(-1)}>
          silence
        </button>
        <button type="button" className={chip} data-on={eventOn} onClick={() => setEventOn((v) => !v)}>
          ⚠ événement Ormuz
        </button>
        <button type="button" className={chip} data-on={frozen} onClick={() => setFrozen((v) => !v)}>
          ⚖ verdict
        </button>
        <button
          type="button"
          className={chip}
          data-on={suspendIran}
          onClick={() => setSuspendIran((v) => !v)}
        >
          🚫 suspendre l&apos;Iran
        </button>
        <button type="button" className={chip} data-on={fogEgypt} onClick={() => setFogEgypt((v) => !v)}>
          🌫 tromper l&apos;Égypte
        </button>
        <button type="button" className={chip} data-on={arcOn} onClick={() => setArcOn((v) => !v)}>
          ➰ arc USA → Iran
        </button>
        <button
          type="button"
          className={chip}
          data-on={view === "2d"}
          onClick={() => setView((v) => (v === "3d" ? "2d" : "3d"))}
        >
          {view === "3d" ? "🗺 déplier (V)" : "🌍 replier (V)"}
        </button>
        <span className="text-fg-faint">
          {thinking
            ? `pense : ${speakerMeta(thinking).label}`
            : speaking
              ? `parle : ${speakerMeta(speaking).label}`
              : "personne ne parle"}
          {picked ? ` · cliqué : ${speakerMeta(picked).label}` : ""}
        </span>
      </div>
    </main>
  );
}
