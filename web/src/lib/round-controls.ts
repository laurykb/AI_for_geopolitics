export function roundButtonLabel({
  spectator,
  accelerationActive,
  active,
  motionPending,
  playedRounds,
}: {
  spectator: boolean;
  accelerationActive: boolean;
  active: boolean;
  motionPending: boolean;
  playedRounds: number;
}): string {
  if (spectator) {
    if (accelerationActive) return "La partie se joue…";
    return playedRounds > 0 ? "Reprendre en accéléré" : "Lancer la partie en accéléré";
  }
  if (active) return "Négociation en cours…";
  if (motionPending) return "Débattre la motion";
  return playedRounds > 0 ? "Continuer la partie" : "Jouer un round";
}

