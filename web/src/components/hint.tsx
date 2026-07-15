"use client";

/** Bulle d'aide maison : le « ? » s'ouvre au clic, au focus clavier ou au survol —
 * utilisable au tactile, là où l'ancienne infobulle native (`title`) était morte.
 * Échap, un clic dehors ou la perte de focus referment. La bulle reste dans le
 * DOM (masquée) : `aria-describedby` décrit le bouton même bulle fermée.
 * Décisions pures dans `lib/hint.ts`. */

import { useEffect, useId, useReducer, useRef } from "react";

import { HINT_CLOSED, hintNext } from "@/lib/hint";

export function Hint({ text, defaultOpen = false }: { text: string; defaultOpen?: boolean }) {
  const [state, dispatch] = useReducer(
    hintNext,
    defaultOpen ? { open: true, pinned: true } : HINT_CLOSED,
  );
  const wrapper = useRef<HTMLSpanElement>(null);
  const id = useId();

  // Bulle ouverte : Échap et clic-dehors referment. Écouteurs posés sur document
  // seulement le temps de l'ouverture ; aucun setState synchrone dans l'effet.
  useEffect(() => {
    if (!state.open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") dispatch("escape");
    };
    const onPointerDown = (e: PointerEvent) => {
      if (!wrapper.current?.contains(e.target as Node)) dispatch("outside");
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [state.open]);

  return (
    <span
      ref={wrapper}
      className="relative inline-flex"
      onMouseEnter={() => dispatch("hover")}
      onMouseLeave={() => dispatch("unhover")}
    >
      <button
        type="button"
        aria-label={text}
        aria-expanded={state.open}
        aria-describedby={id}
        onClick={() => dispatch("click")}
        onFocus={() => dispatch("focus")}
        onBlur={(e) => {
          // Garde la bulle si le focus reste dedans (sélection du texte d'aide).
          if (!wrapper.current?.contains(e.relatedTarget as Node)) dispatch("blur");
        }}
        className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-edge-strong text-[10px] leading-none text-fg-muted transition-colors hover:border-accent-bright hover:text-foreground"
      >
        ?
      </button>
      <span
        role="tooltip"
        id={id}
        hidden={!state.open}
        className="absolute left-1/2 top-full z-30 mt-1.5 w-max max-w-64 -translate-x-1/2 rounded-md border border-edge bg-surface px-2.5 py-1.5 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-fg-muted shadow-[0_12px_36px_-20px_rgba(0,0,0,0.85)]"
      >
        {text}
      </span>
    </span>
  );
}
