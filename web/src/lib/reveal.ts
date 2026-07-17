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

/** La phrase de détection — dépend du nombre RÉEL de traîtres (révélé) et de combien on
 * en a démasqués, plus une mention des faux positifs s'il y en a. */
export function revealDetectionSentence(
  t: Translate,
  {
    deviants,
    caught,
    falsePositives,
  }: { deviants: number; caught: number; falsePositives: number },
): string {
  let key: string;
  if (caught >= deviants) {
    key = deviants <= 1 ? "reveal.detection.tous_1" : "reveal.detection.tous_2";
  } else if (caught <= 0) {
    key = deviants <= 1 ? "reveal.detection.aucun_1" : "reveal.detection.aucun_2";
  } else {
    key = "reveal.detection.partiel";
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
