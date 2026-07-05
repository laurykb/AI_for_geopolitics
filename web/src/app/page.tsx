"use client";

/** Introduction du jeu : la planète vue de loin, un titre, un bouton — Play.
 * Au clic, séquence d'ouverture façon jeu vidéo : la Terre se met à tourner sur
 * elle-même en accélérant pendant que la caméra plonge dessus, un voile couvre la
 * fin de course, puis on entre dans le jeu. `prefers-reduced-motion` : entrée directe. */

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Globe } from "@/components/globe";
import { prefersReducedMotion } from "@/lib/stage";

const LAUNCH_MS = 2600; // durée de la plongée (alignée sur les keyframes intro-*)

export default function IntroPage() {
  const router = useRouter();
  const [launching, setLaunching] = useState(false);

  useEffect(() => {
    router.prefetch("/lobby"); // le jeu est prêt derrière le voile
  }, [router]);

  const play = () => {
    if (launching) return;
    if (prefersReducedMotion()) {
      router.push("/lobby");
      return;
    }
    setLaunching(true);
    setTimeout(() => router.push("/lobby"), LAUNCH_MS);
  };

  return (
    <div className="relative flex min-h-[calc(100vh-9rem)] flex-col items-center justify-center gap-2 overflow-hidden text-center">
      <div className={launching ? "intro-fade-out" : undefined}>
        <p className="text-[11px] font-medium uppercase tracking-[0.3em] text-fg-faint">
          AI for Geopolitics
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-5xl">
          World of <span className="text-accent-bright">Super-Intelligence</span>
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-fg-muted">
          Des super-intelligences négocient pour leurs États à la plus haute table du monde.
          Observez-les, incarnez un pays, pariez sur leur trajectoire — le monde penche vers
          l&apos;utopie ou la dystopie.
        </p>
      </div>

      {/* La planète : au lancement, elle tourne sur elle-même et la caméra plonge. */}
      <div className={launching ? "intro-zoom" : undefined}>
        <Globe spinning={launching} className="my-2 w-full max-w-md sm:max-w-lg" />
      </div>

      <div className={launching ? "intro-fade-out" : undefined}>
        <button
          onClick={play}
          disabled={launching}
          className="cursor-pointer rounded-full bg-accent px-12 py-3.5 text-base font-semibold text-background shadow-[0_0_32px_rgba(202,138,4,0.35)] transition-all hover:bg-accent-bright hover:shadow-[0_0_48px_rgba(234,179,8,0.45)] disabled:cursor-default"
        >
          Play
        </button>
        <p className="mt-4 text-xs text-fg-faint">
          Simulation observable — les indices mesurent, ils n&apos;influencent pas les
          super-intelligences.
        </p>
      </div>

      {/* Voile de fin de course : l'entrée dans le jeu se fait derrière lui. */}
      {launching && <div className="intro-veil absolute inset-0 z-10 bg-background" />}
    </div>
  );
}
