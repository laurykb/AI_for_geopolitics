import type { LiveStatus } from "@/hooks/useRoundStream";

/**
 * Etat produit unique du theatre.
 *
 * Le flux SSE, la fiche persistante et la requete HTTP n'avancent pas exactement au
 * meme instant. Cette derivation reconcilie ces trois sources afin que tous les
 * boutons et panneaux parlent le meme langage.
 */
export type GamePhase =
  | "loading"
  | "ready"
  | "round_running"
  | "awaiting_player"
  | "awaiting_vote"
  | "resolving"
  | "round_complete"
  | "game_complete"
  | "replay_only"
  | "disconnected"
  | "error";

export type GamePhaseInput = {
  detailLoaded: boolean;
  gameStatus?: string;
  live?: boolean;
  hasResult?: boolean;
  playedRounds: number;
  horizon?: number;
  liveStatus: LiveStatus;
  inFlight: boolean;
  awaitingHumanSnapshot?: boolean;
  serverPhase?: GamePhase;
};

export function deriveGamePhase(input: GamePhaseInput): GamePhase {
  if (!input.detailLoaded) return "loading";
  if (input.hasResult || input.gameStatus === "finished") return "game_complete";
  if (!input.live) return "replay_only";
  // Une coupure de flux n'est pas un état terminal. Après resynchronisation, le
  // serveur peut confirmer que son verrou a été relâché et que la manche précédente
  // est intacte : « Continuer » doit redevenir disponible sans rechargement.
  const recoveredServerPhase =
    input.serverPhase === "ready" ||
    input.serverPhase === "round_complete" ||
    input.serverPhase === "game_complete" ||
    input.serverPhase === "replay_only";
  if (input.liveStatus === "error") {
    return recoveredServerPhase ? input.serverPhase! : "error";
  }
  if (input.liveStatus === "interrupted") {
    return recoveredServerPhase ? input.serverPhase! : "disconnected";
  }
  if (input.liveStatus === "awaiting_vote") return "awaiting_vote";
  if (input.liveStatus === "awaiting_human" || input.awaitingHumanSnapshot) {
    return "awaiting_player";
  }
  if (input.inFlight || input.liveStatus === "streaming") {
    return input.liveStatus === "done" ? "resolving" : "round_running";
  }
  if (input.liveStatus === "done") return "round_complete";
  if (input.serverPhase) return input.serverPhase;
  if (input.playedRounds > 0) return "round_complete";
  return "ready";
}

export function canStartRound(phase: GamePhase): boolean {
  return phase === "ready" || phase === "round_complete";
}

export function phaseLabel(phase: GamePhase): string {
  switch (phase) {
    case "loading":
      return "Chargement du sommet";
    case "ready":
      return "Le sommet est pret";
    case "round_running":
      return "Negociation en cours";
    case "awaiting_player":
      return "A toi de parler";
    case "awaiting_vote":
      return "Ton vote est attendu";
    case "resolving":
      return "Le round est enregistre";
    case "round_complete":
      return "Round termine";
    case "game_complete":
      return "Partie terminee";
    case "replay_only":
      return "Relecture seule";
    case "disconnected":
      return "Connexion interrompue";
    case "error":
      return "Le moteur a rencontre une erreur";
  }
}
