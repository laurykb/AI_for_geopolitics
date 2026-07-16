"use client";

/** Navigation du haut : Classement du jour + Informations (+ Admin si is_admin), le
 * pseudo (→ Réglages, G14) et la déconnexion. RG-1 : le classement global par LP a
 * disparu — le lien pointe vers le Défi du jour (/defi), seul classement conservé.
 * L'observatoire public a disparu (G11) : chacun voit SES parties à l'accueil, l'admin
 * voit tout via /admin. Campagne est un mode de jeu (choisi au lancement d'une partie). */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { useT } from "@/components/settings-provider";
import { useTour } from "@/components/tour";

const LINKS = [
  { href: "/accueil", key: "header.accueil" },
  { href: "/defi", key: "header.leaderboard" },
  { href: "/informations", key: "header.informations" },
];

export function HeaderNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { player, signOut } = useAuth();
  const { restart } = useTour();
  const t = useT();

  const links = player?.is_admin ? [...LINKS, { href: "/admin", key: "header.admin" }] : LINKS;

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
          {t(l.key)}
        </Link>
      ))}
      {player && (
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
      )}
    </nav>
  );
}
