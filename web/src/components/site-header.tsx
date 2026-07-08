"use client";

/** Barre de titre + navigation. Masquée sur l'écran de connexion `/` (S0) et le replay
 * public `/r/{id}` : ces vues sont plein-cadre, sans chrome d'application. */

import Link from "next/link";
import { usePathname } from "next/navigation";

import { HeaderNav } from "@/components/header-nav";

export function SiteHeader() {
  const pathname = usePathname();
  if (pathname === "/" || pathname.startsWith("/r/")) return null;

  return (
    <header className="sticky top-0 z-40 border-b border-edge bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-6">
        <Link href="/accueil" className="group flex items-baseline gap-3">
          <span className="text-sm font-semibold tracking-wide">
            Théâtre des super-intelligences
          </span>
          <span className="hidden text-xs text-fg-faint transition-colors group-hover:text-fg-muted sm:inline">
            AI for Geopolitics
          </span>
        </Link>
        <HeaderNav />
      </div>
    </header>
  );
}
