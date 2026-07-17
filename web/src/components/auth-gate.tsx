"use client";

/** Garde d'authentification (G11 §1 S0 : « garde d'auth sur toutes les routes »).
 * Toute route est protégée SAUF l'écran de connexion `/` et le replay public `/r/{id}`
 * (liens partagés, RLS parties publiées). Sans session → retour à l'écran de connexion. */

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth-provider";
import { Spinner } from "@/components/ui";

/** Une route publique n'exige pas de session. */
export function isPublicRoute(pathname: string): boolean {
  return pathname === "/" || pathname.startsWith("/r/");
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { player, loading } = useAuth();
  const publicRoute = isPublicRoute(pathname);

  useEffect(() => {
    if (!publicRoute && !loading && !player) router.replace("/");
  }, [publicRoute, loading, player, router]);

  if (publicRoute) return <>{children}</>;

  if (loading || !player) {
    return (
      <p className="flex items-center gap-2 py-16 text-sm text-fg-muted">
        <Spinner /> {loading ? "Chargement…" : "Redirection vers la connexion…"}
      </p>
    );
  }

  return <>{children}</>;
}
