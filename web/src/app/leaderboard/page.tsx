/** RG-1 — le classement global par points de ligue a disparu (les LP sont retirés). La
 * route /leaderboard redirige vers le « Classement du jour » (le Défi du jour, /defi),
 * le seul classement conservé : tout le monde y joue la même crise, sans monnaie
 * compétitive permanente. On garde la redirection pour les anciens liens/marque-pages. */

import { redirect } from "next/navigation";

export default function LeaderboardPage() {
  redirect("/defi");
}
