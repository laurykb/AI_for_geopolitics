"use client";

/** S0 — Connexion (G11 §1). Le globe qui tourne (l'accueil historique) + un panneau
 * pseudo / mot de passe. Auth Supabase (email technique dérivé, jamais montré) ou repli
 * localStorage `offline`. Une fois connecté → S1 Accueil (`/accueil`). */

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { Globe } from "@/components/globe";
import { useT } from "@/components/settings-provider";
import { Banner, Segmented, Spinner } from "@/components/ui";
import { usePlanetLaunch } from "@/hooks/usePlanetLaunch";
import { startChapter } from "@/lib/api";
import { getAuth } from "@/lib/auth";

export default function ConnexionPage() {
  const router = useRouter();
  const t = useT();
  const { launching, launch } = usePlanetLaunch();
  const { player, loading, offline } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [pseudo, setPseudo] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Déjà connecté (session persistée / reconnexion auto) → droit à l'accueil.
  useEffect(() => {
    if (!loading && player && !busy) router.replace("/accueil");
  }, [busy, loading, player, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const auth = getAuth();
    const result =
      mode === "signin"
        ? await auth.signIn(pseudo, password)
        : await auth.signUp(pseudo, password);
    if (result.ok) {
      launch("/accueil"); // plongée sur la planète → accueil
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
    try {
      const game = await startChapter("sommet-inaugural", result.player.id, "france");
      launch(`/games/${game.id}`);
    } catch {
      launch("/accueil");
    }
  };

  const chrome = launching ? "intro-fade-out" : undefined;

  return (
    <div className="relative flex min-h-[calc(100vh-9rem)] flex-col items-center justify-center gap-6 overflow-hidden py-6 text-center">
      <div className={chrome}>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Théâtre des <span className="text-accent-bright">super-intelligences</span>
        </h1>
        <p className="mt-3 text-sm text-fg-muted">{t("login.pitch")}</p>
      </div>

      <div className={launching ? "intro-zoom" : undefined}>
        <Globe spinning={launching} className="w-full max-w-[300px] sm:max-w-[340px]" />
      </div>

      <div className={`w-full max-w-sm space-y-3 ${chrome ?? ""}`}>
        <button
          type="button"
          onClick={playAsGuest}
          disabled={busy || launching}
          className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-accent px-5 py-3.5 text-base font-semibold text-background shadow-[0_0_36px_rgba(202,138,4,0.28)] transition-all hover:bg-accent-bright hover:shadow-[0_0_48px_rgba(234,179,8,0.38)] disabled:cursor-not-allowed disabled:opacity-50"
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

      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-3 rounded-xl border border-edge bg-surface p-5 text-left shadow-[inset_0_1px_0_0_rgba(248,250,252,0.04),0_12px_32px_-20px_rgba(0,0,0,0.8)]"
      >
        {/* Bascule connexion / création */}
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
            className="w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
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
            className="w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
            required
          />
        </label>

        {error && <Banner tone="bad">{error}</Banner>}

        <button
          type="submit"
          disabled={busy}
          className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
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

      {/* Voile de plongée : couvre l'écran pendant le zoom vers l'accueil. */}
      {launching && <div className="intro-veil absolute inset-0 z-10 bg-background" />}
    </div>
  );
}
