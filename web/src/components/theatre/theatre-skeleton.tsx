import { Skeleton } from "@/components/ui";

/** Squelette de chargement du théâtre : l'espace est réservé (zéro layout shift),
 * le shimmer remplace le « … » du premier rendu. Extrait de page.tsx (découpe). */
export function TheatreSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Théâtre en cours de chargement">
      <header className="space-y-2">
        <Skeleton className="h-3 w-44" />
        <Skeleton className="h-7 w-80 max-w-full" />
      </header>
      <Skeleton className="h-16 w-full rounded-lg" />
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,340px)]">
        <Skeleton className="h-[420px] w-full rounded-lg" />
        <div className="space-y-3">
          <Skeleton className="h-24 w-full rounded-lg" />
          <Skeleton className="h-36 w-full rounded-lg" />
          <Skeleton className="h-28 w-full rounded-lg" />
        </div>
      </div>
    </div>
  );
}
