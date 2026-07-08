"use client";

/** Transition « zoom sur la planète » réutilisable (G12 UI). La Terre plonge (`.intro-zoom`)
 * pendant qu'un voile couvre l'écran, puis on navigue — la même plongée que l'entrée du jeu,
 * rejouée à chaque transition entre les écrans du menu. `prefers-reduced-motion` : navigation
 * directe, sans animation. */

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { prefersReducedMotion } from "@/lib/stage";

const LAUNCH_MS = 2600; // aligné sur .intro-zoom / .intro-veil (globals.css)

export function usePlanetLaunch() {
  const router = useRouter();
  const [launching, setLaunching] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const launch = (href: string) => {
    if (launching) return;
    if (prefersReducedMotion()) {
      router.push(href);
      return;
    }
    setLaunching(true);
    timer.current = setTimeout(() => router.push(href), LAUNCH_MS);
  };

  return { launching, launch };
}
