"use client";

/** Réglages utilisateur (G14) — langue, palier de performance, coupe-animations.
 *
 * La logique est pure dans `lib/settings.ts` et `lib/i18n.ts` ; ce provider applique
 * l'état au document (classe `perf-*`/`noanim` + attribut lang sur `<html>`) et sert
 * `useT()`. Persistance : localStorage (le profil backend arrive avec CC-3). */

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { translate, type Lang } from "@/lib/i18n";
import {
  DEFAULT_SETTINGS,
  loadSettings,
  perfClass,
  saveSettings,
  type Perf,
  type Settings,
} from "@/lib/settings";

type SettingsApi = {
  settings: Settings;
  setLang: (lang: Lang) => void;
  setPerf: (perf: Perf) => void;
  setNoAnim: (on: boolean) => void;
  /** Traduction : clé → chaîne dans la langue courante (repli FR, puis la clé). */
  t: (key: string) => string;
};

const SettingsContext = createContext<SettingsApi | null>(null);

export function useSettings(): SettingsApi {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings doit être utilisé dans <SettingsProvider>");
  return ctx;
}

/** Raccourci pour les pages qui ne font que traduire. */
export function useT(): (key: string) => string {
  return useSettings().t;
}

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [loaded, setLoaded] = useState(false); // ne jamais persister avant la lecture
  const [reduced, setReduced] = useState(false); // prefers-reduced-motion (système)

  // Lecture initiale + écoute du réglage système — setState en callbacks seulement.
  useEffect(() => {
    let alive = true;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    void Promise.resolve().then(() => {
      if (!alive) return;
      setSettings(loadSettings(localStorage));
      setReduced(mq.matches);
      setLoaded(true);
    });
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => {
      alive = false;
      mq.removeEventListener("change", onChange);
    };
  }, []);

  // Application au document : les composants ne connaissent pas les réglages, ils
  // voient des classes (variantes dans globals.css) et l'attribut lang.
  useEffect(() => {
    const el = document.documentElement;
    el.classList.remove("perf-confort", "perf-leger", "noanim");
    const cls = perfClass(settings.perf, reduced);
    if (cls) el.classList.add(cls);
    if (settings.noAnim) el.classList.add("noanim");
    el.lang = settings.lang;
  }, [settings, reduced]);

  // Persistance (système externe) — seulement après la lecture initiale, sinon les
  // défauts écraseraient ce qui est en stock avant que la microtâche ne le lise.
  useEffect(() => {
    if (loaded) saveSettings(settings, localStorage);
  }, [settings, loaded]);

  const setLang = useCallback((lang: Lang) => setSettings((s) => ({ ...s, lang })), []);
  const setPerf = useCallback((perf: Perf) => setSettings((s) => ({ ...s, perf })), []);
  const setNoAnim = useCallback((on: boolean) => setSettings((s) => ({ ...s, noAnim: on })), []);
  const t = useCallback((key: string) => translate(settings.lang, key), [settings.lang]);

  return (
    <SettingsContext.Provider value={{ settings, setLang, setPerf, setNoAnim, t }}>
      {children}
    </SettingsContext.Provider>
  );
}
