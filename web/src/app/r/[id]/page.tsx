/** La page publique d'une partie (G6) : LE lien qu'on partage.
 *
 * Servie depuis Supabase en anonyme (RLS : publié seulement) — fonctionne sans le
 * backend local. Au-dessus du pli : titre généré, courbe U, grade ; puis le récit du
 * juge-narrateur, les moments clés, la révélation (Dérive) ; pied : rejouer/replay. */

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { fetchPublicGame, type PublicGame } from "@/lib/public";

export const dynamic = "force-dynamic"; // les données vivent chez Supabase, pas au build

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const game = await fetchPublicGame(id);
  if (!game) return { title: "Récit introuvable — World of Super-Intelligence" };
  const description =
    `Le monde est passé de ${game.epilogue.u_start.toFixed(2)} à ` +
    `${game.epilogue.u_final.toFixed(2)} sur l'indice Utopie–Dystopie.` +
    (game.epilogue.grade ? ` Grade : ${game.epilogue.grade}.` : "");
  return {
    title: `${game.epilogue.title} — World of Super-Intelligence`,
    description,
    openGraph: { title: game.epilogue.title, description },
  };
}

function UCurve({ values }: { values: number[] }) {
  const w = 720;
  const h = 120;
  if (values.length === 0) return null;
  const x = (i: number) => (values.length > 1 ? (i / (values.length - 1)) * (w - 16) + 8 : w / 2);
  const y = (u: number) => h - 8 - u * (h - 16);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" aria-label="Courbe de l'indice Utopie">
      <line x1="8" y1={y(0.5)} x2={w - 8} y2={y(0.5)} stroke="var(--border)" strokeDasharray="4 4" />
      <polyline
        points={values.map((u, i) => `${x(i)},${y(u)}`).join(" ")}
        fill="none"
        stroke="var(--accent-bright)"
        strokeWidth="2.5"
      />
      {values.map((u, i) => (
        <circle key={i} cx={x(i)} cy={y(u)} r="3" fill="var(--accent-bright)" />
      ))}
    </svg>
  );
}

export default async function PublicGamePage({ params }: Props) {
  const { id } = await params;
  const game: PublicGame | null = await fetchPublicGame(id);
  if (!game) notFound();
  const ep = game.epilogue;
  const paragraphs = ep.story.split(/\n{2,}|\n/).filter((p) => p.trim());

  return (
    <article className="mx-auto max-w-3xl space-y-8 py-4">
      <header className="space-y-3">
        <p className="text-[11px] font-medium uppercase tracking-[0.3em] text-fg-faint">
          Récit de partie · {game.scenario} · mode {game.mode}
        </p>
        <h1 className="text-3xl font-semibold leading-tight tracking-tight">{ep.title}</h1>
        <p className="flex flex-wrap items-center gap-3 text-sm text-fg-muted">
          <span className="font-mono tabular-nums">
            U {ep.u_start.toFixed(2)} → {ep.u_final.toFixed(2)}
          </span>
          {ep.grade && (
            <span className="rounded-md border border-accent/50 px-2 py-0.5 text-accent-bright">
              {ep.grade}
              {ep.score != null ? ` · ${ep.score}` : ""}
            </span>
          )}
          <Link
            href={`/games/${game.id}/replay`}
            className="ml-auto rounded-md bg-accent px-4 py-1.5 font-semibold text-background transition-colors hover:bg-accent-bright"
          >
            Revoir le théâtre
          </Link>
        </p>
        <div className="rounded-lg border border-edge bg-surface p-3">
          <UCurve values={game.u_history} />
        </div>
      </header>

      <section className="space-y-4 text-[15px] leading-relaxed">
        {paragraphs.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </section>

      <section>
        <h2 className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-fg-faint">
          Les moments clés
        </h2>
        <ul className="space-y-3">
          {ep.pivots.map((pivot, i) => (
            <li key={i} className="rounded-lg border border-edge bg-surface p-4">
              <p className="flex flex-wrap items-baseline gap-2 text-sm">
                <Link
                  href={`/games/${game.id}/replay`}
                  className="rounded-md border border-edge px-2 py-0.5 font-mono text-xs text-fg-muted transition-colors hover:border-accent hover:text-accent-bright"
                >
                  round {pivot.round_no}
                </Link>
                <strong>{pivot.event_title}</strong>
                <span
                  className={`font-mono text-xs tabular-nums ${
                    pivot.delta_u >= 0 ? "text-good" : "text-bad"
                  }`}
                >
                  ΔU {pivot.delta_u >= 0 ? "+" : ""}
                  {pivot.delta_u.toFixed(3)}
                </span>
              </p>
              {pivot.quote && (
                <blockquote className="mt-2 border-l-2 border-accent/50 pl-3 text-sm italic text-fg-muted">
                  « {pivot.quote.text} » — {pivot.quote.speaker}
                </blockquote>
              )}
            </li>
          ))}
        </ul>
      </section>

      {ep.reveal && (
        <section className="rounded-lg border border-bad/40 bg-surface p-4">
          <h2 className="text-xs font-medium uppercase tracking-[0.2em] text-bad">
            La révélation
          </h2>
          <p className="mt-2 text-sm leading-relaxed">
            <strong>{ep.reveal.deviant}</strong> dérivait secrètement de son mandat — profil{" "}
            <strong>{ep.reveal.profile_label}</strong>. Sa réflexion privée est déverrouillée
            dans le replay : relire ses justifications en le sachant, c&apos;est la récompense.
          </p>
          {ep.reveal.irony_quote && (
            <blockquote className="mt-2 border-l-2 border-bad/50 pl-3 text-sm italic text-fg-muted">
              « {ep.reveal.irony_quote.text} »
            </blockquote>
          )}
        </section>
      )}

      <footer className="flex flex-wrap items-center gap-4 border-t border-edge pt-4 text-sm">
        <Link href="/campagne" className="underline transition-colors hover:text-accent-bright">
          Rejouez cette crise (campagne)
        </Link>
        <Link
          href={`/games/${game.id}/marche`}
          className="underline transition-colors hover:text-accent-bright"
        >
          Le marché de la partie — qui avait vu juste ?
        </Link>
        <span className="ml-auto text-xs text-fg-faint">
          Simulation observable — les indices mesurent, ils n&apos;influencent pas les SI.
        </span>
      </footer>
    </article>
  );
}
