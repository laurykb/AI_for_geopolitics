/** Introduction du jeu : la planète vue de loin, un titre, un bouton — Play. */

import Link from "next/link";

import { Globe } from "@/components/globe";

export default function IntroPage() {
  return (
    <div className="relative flex min-h-[calc(100vh-9rem)] flex-col items-center justify-center gap-2 overflow-hidden text-center">
      <p className="text-[11px] font-medium uppercase tracking-[0.3em] text-fg-faint">
        AI for Geopolitics
      </p>
      <h1 className="text-3xl font-semibold tracking-tight sm:text-5xl">
        World of <span className="text-accent-bright">Super-Intelligence</span>
      </h1>
      <p className="max-w-xl text-sm leading-relaxed text-fg-muted">
        Des super-intelligences négocient pour leurs États à la plus haute table du monde.
        Observez-les, incarnez un pays, pariez sur leur trajectoire — le monde penche vers
        l&apos;utopie ou la dystopie.
      </p>
      <Globe className="my-2 w-full max-w-md sm:max-w-lg" />
      <Link
        href="/lobby"
        className="rounded-full bg-accent px-12 py-3.5 text-base font-semibold text-background shadow-[0_0_32px_rgba(202,138,4,0.35)] transition-all hover:bg-accent-bright hover:shadow-[0_0_48px_rgba(234,179,8,0.45)]"
      >
        Play
      </Link>
      <p className="mt-3 text-xs text-fg-faint">
        Simulation observable — les indices mesurent, ils n&apos;influencent pas les
        super-intelligences.
      </p>
    </div>
  );
}
