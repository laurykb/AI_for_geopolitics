"use client";

/** Navigation d'une partie : Théâtre / Marché / Revoir. Le monde a fusionné avec le
 * théâtre (G1 : la carte est le théâtre) — /monde redirige. Libellés i18n (CC-15b) :
 * « le théâtre » est LE nom de l'écran de jeu, « Revoir » celui de la relecture. */

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useT } from "./settings-provider";

const TABS = [
  { slug: "", key: "gamenav.theatre" },
  { slug: "marche", key: "gamenav.marche" },
  { slug: "replay", key: "gamenav.revoir" },
] as const;

export function GameNav({ id }: { id: string }) {
  const pathname = usePathname();
  const t = useT();
  return (
    <nav aria-label={t("gamenav.aria")} className="flex gap-1 rounded-lg border border-edge bg-surface p-1">
      {TABS.map((tab) => {
        const href = tab.slug ? `/games/${id}/${tab.slug}` : `/games/${id}`;
        const active = pathname === href;
        return (
          <Link
            key={tab.slug}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              active
                ? "bg-surface-2 text-accent-bright"
                : "text-fg-muted hover:bg-surface-2/60 hover:text-foreground"
            }`}
          >
            {t(tab.key)}
          </Link>
        );
      })}
    </nav>
  );
}
