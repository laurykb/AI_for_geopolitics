"use client";

/** Navigation du haut : Classement du jour + Informations (+ Admin si is_admin), le
 * pseudo (→ Réglages, G14) et la déconnexion. RG-1 : le classement global par LP a
 * disparu — le lien pointe vers le Défi du jour (/defi), seul classement conservé.
 * L'observatoire public a disparu (G11) : chacun voit SES parties à l'accueil, l'admin
 * voit tout via /admin. Campagne et Laboratoire sont des modes de jeu choisis depuis
 * « Nouvelle partie » : ils n'ont pas d'entrée dédiée dans le header. */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useT } from "@/components/settings-provider";
import { useTour } from "@/components/tour";

export const HEADER_LINKS = [
  { href: "/", key: "header.accueil" },
  { href: "/defi", key: "header.leaderboard" },
  { href: "/informations", key: "header.informations" },
];

export function HeaderNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { player, signOut } = useAuth();
  const { restart } = useTour();
  const t = useT();
  const [mobileOpen, setMobileOpen] = useState(false);

  const links = player?.is_admin
    ? [...HEADER_LINKS, { href: "/admin", key: "header.admin" }]
    : HEADER_LINKS;

  const onSignOut = async () => {
    await signOut();
    router.replace("/");
  };

  const navigationLinks = links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          onClick={() => setMobileOpen(false)}
          aria-current={pathname === l.href ? "page" : undefined}
          className={`py-1 transition-colors hover:text-foreground ${
            pathname === l.href
              ? "text-accent-bright underline decoration-accent-bright/60 decoration-2 underline-offset-8"
              : ""
          }`}
        >
          {t(l.key)}
        </Link>
      ));

  const playerActions = player && (
        <span className="flex items-center gap-3 border-l border-edge pl-5">
          <button
            onClick={restart}
            title={t("header.visite")}
            aria-label={t("header.visite")}
            className="grid h-6 w-6 cursor-pointer place-items-center rounded-full border border-edge text-xs text-fg-muted transition-colors hover:border-accent hover:text-accent-bright"
          >
            ?
          </button>
          <Link
            href="/reglages"
            title={t("header.reglages")}
            aria-current={pathname === "/reglages" ? "page" : undefined}
            className={`hidden text-xs transition-colors hover:text-foreground sm:inline ${
              pathname === "/reglages" ? "text-accent-bright" : "text-fg-faint"
            }`}
          >
            {player.pseudo}
          </Link>
          <button
            onClick={onSignOut}
            className="cursor-pointer rounded-md border border-edge px-2.5 py-1 text-xs text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
          >
            {t("header.deconnexion")}
          </button>
        </span>
      );

  return (
    <>
      <nav className="hidden items-center gap-5 text-sm text-fg-muted md:flex">
        {navigationLinks}
        {playerActions}
      </nav>
      <div className="md:hidden">
        <button
          type="button"
          aria-expanded={mobileOpen}
          aria-controls="mobile-navigation"
          onClick={() => setMobileOpen((open) => !open)}
          className="inline-flex h-9 items-center gap-2 rounded-md border border-edge px-3 text-xs font-semibold text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
        >
          <span aria-hidden="true">{mobileOpen ? "×" : "☰"}</span>
          {t("header.menu")}
        </button>
        {mobileOpen && (
          <nav
            id="mobile-navigation"
            aria-label={t("header.menu")}
            className="absolute inset-x-3 top-[3.25rem] z-50 grid gap-1 rounded-xl border border-edge bg-background/95 p-3 text-sm text-fg-muted shadow-2xl backdrop-blur"
          >
            {navigationLinks}
            {player && (
              <>
                <div className="my-1 border-t border-edge" />
                <Link href="/reglages" className="py-1 transition-colors hover:text-foreground">
                  {player.pseudo} · {t("header.reglages")}
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    setMobileOpen(false);
                    restart();
                  }}
                  className="py-1 text-left transition-colors hover:text-foreground"
                >
                  {t("header.visite")}
                </button>
                <button
                  type="button"
                  onClick={onSignOut}
                  className="py-1 text-left transition-colors hover:text-foreground"
                >
                  {t("header.deconnexion")}
                </button>
              </>
            )}
          </nav>
        )}
      </div>
    </>
  );
}
