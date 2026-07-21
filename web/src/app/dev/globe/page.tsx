"use client";

/** Atelier de développement du théâtre-globe (runbook S1-S2) — PAS une surface
 * du jeu : aucune navigation n'y mène, la page sert à itérer visuellement sur
 * `GlobeStage` avec l'app qui tourne, avant son branchement au théâtre (S3-S4).
 * Les boutons simulent les états du direct (orateur, pensée) à la main. */

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

export default function GlobeDevPage() {
  const [speakerIdx, setSpeakerIdx] = useState<number>(-1);
  const [picked, setPicked] = useState<string | null>(null);
  const speaking = speakerIdx >= 0 ? SUMMIT[speakerIdx % SUMMIT.length] : null;

  return (
    <main className="fixed inset-0 bg-[#04060c]">
      <GlobeStage
        countries={SUMMIT}
        uByCountry={U_BY_COUNTRY}
        utopia={0.52}
        speaking={speaking}
        onCountryClick={setPicked}
        className="h-full w-full"
      />
      <div className="absolute bottom-4 left-4 z-10 flex items-center gap-2 rounded-lg border border-edge bg-surface/85 px-3 py-2 text-xs text-foreground backdrop-blur">
        <button
          type="button"
          className="rounded border border-edge px-2 py-1 hover:bg-surface"
          onClick={() => setSpeakerIdx((i) => i + 1)}
        >
          🗣 orateur suivant
        </button>
        <button
          type="button"
          className="rounded border border-edge px-2 py-1 hover:bg-surface"
          onClick={() => setSpeakerIdx(-1)}
        >
          silence
        </button>
        <span className="text-fg-faint">
          {speaking ? `parle : ${speakerMeta(speaking).label}` : "personne ne parle"}
          {picked ? ` · cliqué : ${speakerMeta(picked).label}` : ""}
        </span>
      </div>
    </main>
  );
}
