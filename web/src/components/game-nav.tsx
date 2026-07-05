"use client";

/** Navigation d'une partie : Théâtre / Monde / Marché / Replay. */

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { slug: "", label: "Théâtre" },
  { slug: "monde", label: "Monde" },
  { slug: "marche", label: "Marché" },
  { slug: "replay", label: "Replay" },
] as const;

export function GameNav({ id }: { id: string }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Sections de la partie" className="flex gap-1 rounded-lg border border-edge bg-surface p-1">
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
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
