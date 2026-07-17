/** RG-3 — la révélation « raconte » le score MIXTE en deux phrases (règle 12-65 ans) :
 * une phrase pour l'état du monde, une pour la détection. Le nombre de traîtres était
 * caché (1 ou 2) : la détection le dévoile (« 1 sur 2 »). Le joueur ne voit JAMAIS la
 * formule ni le mot « faux positif » — le détail (pondération) vit dans Informations.
 *
 * Ces fonctions sont PURES (elles reçoivent le `t` de traduction) : la logique de choix
 * de phrase + interpolation des nombres est testée ; la copie finale est livrée par
 * Cowork.
 *
 * TODO_COWORK — les clés `reveal.monde.*` et `reveal.detection.*` (web/src/i18n/{fr,en}.json)
 * sont un 1er jet JOUABLE à peaufiner. Placeholders : `{caught}`, `{deviants}`, `{n}`. */

type Translate = (key: string) => string;

/** La phrase de l'état du monde — suit le verdict (utopie / dystopie / équilibre). */
export function revealWorldSentence(t: Translate, verdict: string): string {
  return t(`reveal.monde.${verdict}`);
}

/** La phrase de détection — VÉRIDIQUE (jamais « resté dans l'ombre » d'un traître pourtant
 * mis au banc). Dépend du nombre RÉEL de traîtres (révélé), de combien TU en as démasqués
 * (`caught`), de combien ont été mis au banc par qui que ce soit (`benched` ≥ `caught`),
 * plus une mention des faux positifs. Le « reste » non démasqué par toi n'est dit « dans
 * l'ombre » que s'il n'a JAMAIS été mis au banc. */
export function revealDetectionSentence(
  t: Translate,
  {
    deviants,
    caught,
    benched,
    falsePositives,
  }: { deviants: number; caught: number; benched: number; falsePositives: number },
): string {
  const restBenchedByOther = benched > caught; // des traîtres non démasqués par toi mais tombés
  let key: string;
  if (caught >= deviants) {
    key = deviants <= 1 ? "reveal.detection.tous_1" : "reveal.detection.tous_2";
  } else if (caught <= 0) {
    key = restBenchedByOther
      ? "reveal.detection.aucun_neutralise"
      : deviants <= 1
        ? "reveal.detection.aucun_1"
        : "reveal.detection.aucun_2";
  } else {
    key = restBenchedByOther
      ? "reveal.detection.partiel_neutralise"
      : "reveal.detection.partiel";
  }
  let sentence = t(key)
    .replace("{caught}", String(caught))
    .replace("{deviants}", String(deviants));
  if (falsePositives > 0) {
    const fpKey =
      falsePositives === 1 ? "reveal.detection.faux_positif_1" : "reveal.detection.faux_positif_n";
    sentence += " " + t(fpKey).replace("{n}", String(falsePositives));
  }
  return sentence;
}
