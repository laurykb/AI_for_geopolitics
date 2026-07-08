"use client";

/** Contexte d'authentification du client WoSI (G11 §1 S0). Porte le joueur connecté
 * (pseudo, rang/LP, is_admin), l'état de chargement et le flag `offline`. Placé haut
 * dans l'arbre (layout) pour que la nav et la garde de routes le lisent. */

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { getAuth, type Player } from "@/lib/auth";

type AuthState = {
  player: Player | null;
  loading: boolean;
  offline: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [player, setPlayer] = useState<Player | null>(null);
  const [loading, setLoading] = useState(true);
  const auth = getAuth();

  const refresh = useCallback(async () => {
    setPlayer(await auth.getPlayer());
  }, [auth]);

  useEffect(() => {
    let alive = true;
    auth.getPlayer().then((p) => {
      if (alive) {
        setPlayer(p);
        setLoading(false);
      }
    });
    const unsub = auth.onChange((p) => alive && setPlayer(p));
    return () => {
      alive = false;
      unsub();
    };
  }, [auth]);

  const signOut = useCallback(async () => {
    await auth.signOut();
    setPlayer(null);
  }, [auth]);

  return (
    <AuthContext.Provider value={{ player, loading, offline: auth.offline, refresh, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

/** Lit le contexte d'auth ; erreur claire si utilisé hors du provider. */
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans <AuthProvider>");
  return ctx;
}
