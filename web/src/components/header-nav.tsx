"use client";

/** Navigation du haut : Observatoire (les parties) + Informations.
 * Masquée sur la page d'introduction (`/`) — le joueur entre par Play, sans détour. */

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/observatoire", label: "Observatoire" },
  { href: "/informations", label: "Informations" },
];

export function HeaderNav() {
  const pathname = usePathname();
  if (pathname === "/") return null; // vue d'introduction : rien d'autre que Play

  return (
    <nav className="flex items-center gap-5 text-sm text-fg-muted">
      {LINKS.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          aria-current={pathname === l.href ? "page" : undefined}
          className={`transition-colors hover:text-foreground ${
            pathname === l.href ? "text-accent-bright" : ""
          }`}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
