"use client";

/** ShellMain — le conteneur de contenu, conscient de la coquille (spec coquille §2).
 *
 * Sur `/` (la coquille : connexion/hall/config), le contenu est plein-cadre et
 * `pointer-events-none` pour que les clics traversent vers le globe (`StageShell`
 * devient cliquable en phase config) ; les overlays réactivent `pointer-events`
 * sur leurs panneaux. Ailleurs, la colonne centrée habituelle (interactive). */

import { usePathname } from "next/navigation";

import { AuthGate } from "@/components/auth-gate";

export function ShellMain({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const shell = pathname === "/";

  return (
    <main
      id="contenu"
      className={
        shell
          ? "pointer-events-none fixed inset-0 z-10"
          : "mx-auto w-full max-w-6xl flex-1 px-6 py-8"
      }
    >
      <AuthGate>{children}</AuthGate>
    </main>
  );
}
