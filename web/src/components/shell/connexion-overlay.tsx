"use client";

/** L'espace connexion, posé sur le globe persistant (spec coquille §4, Inc 2-3).
 *
 * Reprend l'auth de l'ancien `app/page.tsx` (pseudo/mot de passe Supabase ou repli
 * offline, « jouer sans compte ») MAIS ne monte plus son propre globe et ne NAVIGUE
 * plus : au succès, `refresh()` fait apparaître le joueur et `/` bascule en phase hall
 * sur place (les délégués se posent sur le monde). Panneau de verre centré. */

import { useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useT } from "@/components/settings-provider";
import { Banner, Segmented, Spinner } from "@/components/ui";
import { getAuth } from "@/lib/auth";

export function ConnexionOverlay() {
  const t = useT();
  const { offline, refresh } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [pseudo, setPseudo] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const auth = getAuth();
    const result =
      mode === "signin" ? await auth.signIn(pseudo, password) : await auth.signUp(pseudo, password);
    if (result.ok) {
      await refresh(); // le joueur apparaît → `/` passe en phase hall (pas de navigation)
    } else {
      setError(result.error);
      setBusy(false);
    }
  };

  const playAsGuest = async () => {
    setBusy(true);
    setError(null);
    const result = await getAuth().continueAsGuest();
    if (!result.ok) {
      setError(result.error);
      setBusy(false);
      return;
    }
    await refresh(); // idem : on atterrit dans le hall (plus de plongée directe en partie)
  };

  return (
    <div className="pointer-events-auto relative mx-auto flex min-h-screen max-w-6xl flex-col items-center justify-center gap-6 px-6 py-6 text-center">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight drop-shadow sm:text-4xl">
          Théâtre des <span className="text-accent-bright">super-intelligences</span>
        </h1>
        <p className="mt-3 text-sm text-fg-muted">{t("login.pitch")}</p>
      </div>

      <div className="w-full max-w-sm space-y-3">
        <button
          type="button"
          onClick={playAsGuest}
          disabled={busy}
          className="thk-cta thk-cut-sm flex w-full items-center justify-center gap-2 text-base font-semibold"
        >
          {busy && <Spinner />}
          Jouer maintenant — sans compte
        </button>
        <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-[11px] text-fg-faint">
          <span>Première décision en moins d&apos;une minute</span>
          <span>Progression locale temporaire</span>
        </div>
      </div>

      <div className="flex w-full max-w-sm items-center gap-3 text-[10px] uppercase tracking-[0.14em] text-fg-faint">
        <span className="h-px flex-1 bg-edge" />
        ou sauvegarder sa progression
        <span className="h-px flex-1 bg-edge" />
      </div>

      <form onSubmit={submit} className="thk-panel thk-cut w-full max-w-sm space-y-3 p-5 text-left">
        <div className="mb-1">
          <Segmented
            ariaLabel="Connexion ou création de compte"
            value={mode}
            onChange={(m) => {
              setMode(m);
              setError(null);
            }}
            options={[
              { value: "signin", label: "Se connecter" },
              { value: "signup", label: "Créer un compte" },
            ]}
          />
        </div>

        <label className="block text-sm">
          <span className="mb-1 block text-xs text-fg-muted">Pseudo</span>
          <input
            value={pseudo}
            onChange={(e) => setPseudo(e.target.value)}
            autoComplete="username"
            placeholder={t("login.pseudo-ph")}
            className="thk-input text-sm"
            required
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-xs text-fg-muted">Mot de passe</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            className="thk-input text-sm"
            required
          />
        </label>

        {error && <Banner tone="bad">{error}</Banner>}

        <button
          type="submit"
          disabled={busy}
          className="thk-cta thk-cut-sm flex w-full items-center justify-center gap-2 text-sm font-semibold"
        >
          {busy && <Spinner />}
          {mode === "signin" ? "Se connecter" : "Créer mon compte"}
        </button>

        <p className="text-center text-xs text-fg-faint">
          {offline
            ? "Mode local — ton compte reste sur cet appareil."
            : "Ton pseudo est ce que voient les autres joueurs ; aucun email requis."}
        </p>
      </form>
    </div>
  );
}
