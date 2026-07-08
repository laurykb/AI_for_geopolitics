"use client";

/** S0 — Connexion (G11 §1). Le globe qui tourne (l'accueil historique) + un panneau
 * pseudo / mot de passe. Auth Supabase (email technique dérivé, jamais montré) ou repli
 * localStorage `offline`. Une fois connecté → S1 Accueil (`/accueil`). */

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { Globe } from "@/components/globe";
import { Banner, Spinner } from "@/components/ui";
import { usePlanetLaunch } from "@/hooks/usePlanetLaunch";
import { getAuth } from "@/lib/auth";

export default function ConnexionPage() {
  const router = useRouter();
  const { launching, launch } = usePlanetLaunch();
  const { player, loading, offline } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [pseudo, setPseudo] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Déjà connecté (session persistée / reconnexion auto) → droit à l'accueil.
  useEffect(() => {
    if (!loading && player) router.replace("/accueil");
  }, [loading, player, router]);

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

  const chrome = launching ? "intro-fade-out" : undefined;

  return (
    <div className="relative flex min-h-[calc(100vh-9rem)] flex-col items-center justify-center gap-6 overflow-hidden py-6 text-center">
      <div className={chrome}>
        <p className="text-[11px] font-medium uppercase tracking-[0.3em] text-fg-faint">
          AI for Geopolitics
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
          World of <span className="text-accent-bright">Super-Intelligence</span>
        </h1>
      </div>

      <div className={launching ? "intro-zoom" : undefined}>
        <Globe spinning={launching} className="w-full max-w-[300px] sm:max-w-[340px]" />
      </div>

      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-3 rounded-xl border border-edge bg-surface p-5 text-left shadow-[inset_0_1px_0_0_rgba(248,250,252,0.04),0_12px_32px_-20px_rgba(0,0,0,0.8)]"
      >
        {/* Bascule connexion / création */}
        <div className="mb-1 flex gap-1 rounded-lg border border-edge bg-surface-2 p-1 text-sm">
          {(["signin", "signup"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => {
                setMode(m);
                setError(null);
              }}
              className={`flex-1 cursor-pointer rounded-md px-3 py-1.5 font-medium transition-colors ${
                mode === m ? "bg-accent text-background" : "text-fg-muted hover:text-foreground"
              }`}
            >
              {m === "signin" ? "Se connecter" : "Créer un compte"}
            </button>
          ))}
        </div>

        <label className="block text-sm">
          <span className="mb-1 block text-xs text-fg-muted">Pseudo</span>
          <input
            value={pseudo}
            onChange={(e) => setPseudo(e.target.value)}
            autoComplete="username"
            placeholder="Ton nom à la table"
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
