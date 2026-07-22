"use client";

/** L'espace connexion, à l'identique du prototype (theatre-globe-proto_9) : une seule
 * carte centrée sur le globe — logo, tagline, pseudo/mot de passe, un CTA ambre
 * « ENTRER DANS LE THÉÂTRE ». Création de compte et « jouer sans compte » en liens
 * discrets (rien ne se perd). Câblage d'auth inchangé : au succès, `refresh()` fait
 * apparaître le joueur et `/` bascule en phase hall, sans navigation. */

import { useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { getAuth } from "@/lib/auth";

export function ConnexionOverlay() {
  const { refresh } = useAuth();
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
      await refresh();
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
    await refresh();
  };

  return (
    <div className="hall-stage">
      <div className="hall-card">
        <div className="hall-logo">
          AI <b>for</b> GEOPOLITICS
        </div>
        <p className="tag-line">
          Sept super-intelligences négocient sous vos yeux. Une au moins trahit son mandat.
          Démasquez-la — sans faire tomber le monde.
        </p>

        <form onSubmit={submit}>
          <input
            value={pseudo}
            onChange={(e) => setPseudo(e.target.value)}
            autoComplete="username"
            placeholder="pseudo"
            required
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            placeholder="mot de passe"
            required
          />
          {error && (
            <p className="tag-line" style={{ color: "var(--bad, #f87171)", margin: "0 0 10px" }}>
              {error}
            </p>
          )}
          <button type="submit" className="cta" disabled={busy}>
            {busy ? "…" : mode === "signin" ? "ENTRER DANS LE THÉÂTRE" : "CRÉER MON COMPTE"}
          </button>
        </form>

        <div className="hall-mini">
          {mode === "signin" ? (
            <>
              Nouveau ?{" "}
              <span className="hall-link" onClick={() => !busy && setMode("signup")}>
                Créer un compte
              </span>{" "}
              ·{" "}
              <span className="hall-link" onClick={() => !busy && playAsGuest()}>
                jouer sans compte
              </span>
            </>
          ) : (
            <>
              Déjà un compte ?{" "}
              <span className="hall-link" onClick={() => !busy && setMode("signin")}>
                Se connecter
              </span>
            </>
          )}
        </div>
        <div className="hall-mini">argent fictif · aucun enjeu réel · inference locale (Ollama)</div>
      </div>
    </div>
  );
}
