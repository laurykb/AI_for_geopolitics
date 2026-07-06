"use client";

/** Introduction du jeu : la planète vue de loin, un titre, un bouton — Play.
 *
 * Play → séquence d'ouverture façon jeu vidéo : la Terre tourne sur elle-même en
 * accélérant pendant que la caméra plonge, un voile couvre la fin de course, puis
 * on entre dans le jeu. Retour au menu (`/?retour=1`) → séquence inverse : on
 * ressort de l'atmosphère, la rotation décélère, le titre revient.
 * `prefers-reduced-motion` : entrées directes, sans séquence. */

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Globe } from "@/components/globe";
import { prefersReducedMotion } from "@/lib/stage";

const LAUNCH_MS = 2600; // plongée (alignée sur .intro-zoom)
const ARRIVE_MS = 2200; // dézoom du retour (aligné sur .intro-unzoom)

export default function IntroPage() {
  const router = useRouter();
  const [launching, setLaunching] = useState(false);
  const [arriving, setArriving] = useState(false);

  useEffect(() => {
    router.prefetch("/lobby"); // le jeu est prêt derrière le voile
    // Retour depuis le jeu : jouer l'animation inverse puis nettoyer l'URL.
    if (new URLSearchParams(window.location.search).has("retour") && !prefersReducedMotion()) {
      window.history.replaceState(null, "", "/");
      const begin = setTimeout(() => setArriving(true), 0);
      const end = setTimeout(() => setArriving(false), ARRIVE_MS);
      return () => {
        clearTimeout(begin);
        clearTimeout(end);
      };
    }
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

  const chrome = launching ? "intro-fade-out" : arriving ? "intro-fade-in" : undefined;

  return (
    <div className="relative flex min-h-[calc(100vh-9rem)] flex-col items-center justify-center gap-2 overflow-hidden text-center">
      <div className={chrome}>
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

      {/* La planète : plongée au lancement, dézoom au retour. */}
      <div className={launching ? "intro-zoom" : arriving ? "intro-unzoom" : undefined}>
        <Globe
          spinning={launching}
          arriving={arriving}
          className="my-2 w-full max-w-md sm:max-w-lg"
        />
      </div>

      <div className={chrome}>
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

      {/* Voiles : couvrent l'entrée dans le jeu, découvrent le retour au menu. */}
      {launching && <div className="intro-veil absolute inset-0 z-10 bg-background" />}
      {arriving && <div className="intro-veil-out absolute inset-0 z-10 bg-background" />}
    </div>
  );
}
