"use client";

/** Navigation du haut : Campagne + Informations (+ Admin si is_admin), le pseudo et
 * la déconnexion. L'observatoire public a disparu (G11) : chacun voit SES parties à
 * l'accueil, l'admin voit tout via /admin. */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";

const LINKS = [
  { href: "/accueil", label: "Accueil" },
  { href: "/campagne", label: "Campagne" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/informations", label: "Informations" },
];

export function HeaderNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { player, signOut } = useAuth();

  const links = player?.is_admin ? [...LINKS, { href: "/admin", label: "Admin" }] : LINKS;

  const onSignOut = async () => {
    await signOut();
    router.replace("/");
  };

  return (
    <nav className="flex items-center gap-5 text-sm text-fg-muted">
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          aria-current={pathname === l.href ? "page" : undefined}
          className={`py-1 transition-colors hover:text-foreground ${
            pathname === l.href
              ? "text-accent-bright underline decoration-accent-bright/60 decoration-2 underline-offset-8"
              : ""
          }`}
        >
          {l.label}
        </Link>
      ))}
      {player && (
        <span className="flex items-center gap-3 border-l border-edge pl-5">
          <span className="hidden text-xs text-fg-faint sm:inline">{player.pseudo}</span>
          <button
            onClick={onSignOut}
            className="cursor-pointer rounded-md border border-edge px-2.5 py-1 text-xs text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
          >
            Se déconnecter
          </button>
        </span>
      )}
    </nav>
  );
}
