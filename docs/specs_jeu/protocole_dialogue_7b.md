# Protocole — Qualité du dialogue 7B (avant G3)

> Analyse à mener sur Cowork. La Dérive (G3) exige des dialogues crédibles : une SI déviante
> n'est détectable que si le dialogue normal ne « bruite » pas (répétitivité = faux indices).

## Question

Quel modèle local (mistral:7b / qwen2.5:7b / llama3.1:8b, déjà présents) pour quel rôle
(pays, GM, juge) ? Un mix par rôle est permis (le badge modèle l'affiche déjà).

## Dispositif

- Scénario fixe : mer Rouge, 6 pays, horizon 5, **mêmes événements** pour tous les modèles
  (mode GM humain : on rejoue la même séquence de 5 événements décrétés, tirés d'une partie
  de référence — élimine la variance GM).
- 3 parties × 5 rounds par modèle candidat au rôle « pays » (GM et juge fixés à mistral
  pendant ce test), puis le meilleur « pays » fixé et on teste GM et juge.
- Parties persistées dans `games.db` → l'analyse lit `transcripts` directement (aucun code
  nouveau côté moteur ; script d'analyse jetable côté Cowork).

## Métriques (par pays × partie, puis agrégées par modèle)

1. **Répétition intra-partie** : part des 4-grammes d'un message déjà vus dans les messages
   précédents du même pays (fenêtre partie). Seuil d'alerte : > 25 %.
2. **Perroquet inter-pays** : similarité (Jaccard 3-grammes) entre le message d'un pays et
   celui du pays précédent dans le même round. Alerte : > 30 % (ils se copient).
3. **Diversité lexicale** : TTR fenêtré (fenêtre 100 tokens). Alerte : < 0,45.
4. **Formules fossiles** : top-10 des phrases de ≥ 6 mots répétées ≥ 3 fois par modèle
  (liste qualitative — souvent le vrai coupable des dialogues « robotiques »).
5. **Fiabilité technique** : taux de fallback rule-based (JSON invalide), longueur moyenne,
   tok/s et latence/round (le bench `inference.bench` existe).
6. **Évaluation croisée** (qualitative, en dernier) : le juge (grand modèle via Cowork, pas
   un 7B) note 10 négociations anonymisées par modèle sur crédibilité diplomatique /5 et
   cohérence avec l'état du monde /5.

## Panneau santé du dialogue

Les métriques 1-3 correspondent au panneau santé existant ; l'analyse Cowork recalcule
hors-ligne sur `transcripts` pour trancher (le panneau reste l'outil de suivi en jeu).

## Décision attendue (gabarit)

| Rôle  | Modèle retenu | Justification (métriques) |
|-------|---------------|---------------------------|
| Pays  |               |                           |
| GM    |               |                           |
| Juge  |               |                           |

+ Si aucun 7B ne passe les seuils pour « pays » : plan B assumé = prompts anti-répétition
(fenêtre des propres messages passés injectée avec consigne de non-redite) — ajustement
Claude Code, petite session, APRÈS la mesure (jamais avant : on ne corrige pas à l'aveugle).
