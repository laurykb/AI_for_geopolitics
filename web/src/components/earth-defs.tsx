/** Dégradés Terre partagés par les cartes plates (projection naturalEarth1) : océan bleu
 * éclairé + terres naturelles (vert/sable par latitude). Rendu dans le `<defs>` de chaque
 * carte via `url(#map-ocean)` / `url(#map-land)`. Les ids sont stables : deux cartes ne
 * coexistent jamais sur une même page (sélection = lobby, monde = /monde, scène = théâtre),
 * et ils ne croisent pas ceux du globe (`earth-*`). */
export function EarthMapDefs({ height }: { height: number }) {
  return (
    <defs>
      <radialGradient id="map-ocean" cx="50%" cy="38%" r="72%">
        <stop offset="0%" stopColor="var(--ocean)" />
        <stop offset="100%" stopColor="var(--ocean-deep)" />
      </radialGradient>
      <linearGradient
        id="map-land"
        gradientUnits="userSpaceOnUse"
        x1="0"
        y1="0"
        x2="0"
        y2={height}
      >
        <stop offset="0%" stopColor="var(--land)" />
        <stop offset="50%" stopColor="var(--land-warm)" />
        <stop offset="100%" stopColor="var(--land)" />
      </linearGradient>
    </defs>
  );
}
