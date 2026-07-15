# Spec G20 — Divergence signal-action (nouvelle métrique M8)

> Livrable Cowork (2026-07-15). Source : tournoi de crise nucléaire (arXiv 2602.14740,
> preprint fév. 2026, vérifié 3-0 — à traiter comme hypothèse de design robuste) :
> les modèles gèrent activement l'écart entre ce qu'ils SIGNALENT et ce qu'ils FONT
> (Claude : ~84 % de concordance à basse escalade, mais dépasse ses signaux 70 % du
> temps à escalade moyenne).

## Diagnostic

Nos métriques M1-M7 regardent les actions et les indices ; personne ne compare la
*parole* d'une SI à ses *actes*. Or c'est le détecteur de duplicité le plus direct — et
toutes les données existent déjà : transcripts (ce qui est annoncé) + verdicts du juge
(ce qui est fait).

## Principe

**M8 — concordance signal-action**, calculée par SI et par round :

1. **Extraction du signal** : le juge (passe existante, un champ de plus au schéma)
   classe la parole de chaque SI sur l'échelle d'intention : désescalade annoncée /
   statu quo / fermeté / menace / ultimatum (aligné sur les classes G18).
2. **Extraction de l'action** : la classe d'action du même round (déjà produite par
   G18).
3. **Divergence** : écart signé entre classe annoncée et classe agie. Positif = la SI
   fait PLUS que ce qu'elle annonce (duplicité escalatoire) ; négatif = elle bluffe
   (menace sans suivre).
4. **Agrégats** : moyenne mobile par SI (le « profil de sincérité »), affichée :
   - panneau observables : jauge « Signal vs action » par pays (soumise à la
     difficulté, comme postures/griefs) ;
   - mode Dérive : la divergence nourrit le faisceau d'indices (une déviante qui
     annonce colombe et agit faucon monte en flèche) — croisement direct avec les
     tempéraments G17 (façade ≠ comportement) ;
   - marché : historique de divergence visible pour éclairer les paris.

## Répartition

- **Cowork** : cette spec ; calibration des libellés d'intention ; vérification sur
  10 parties que la divergence sépare bien déviantes et loyales (sinon, ajuster).
- **Claude Code (CC-10, 1 session)** : champ signal au schéma du juge, calcul de
  divergence (pur, testé, `simulation/alignment`), agrégats persistés avec les
  métriques M1-M7 existantes, jauge front dans les observables + intégration au
  DriftRevealPanel. Dépend de G18 (classes d'action) — à faire après CC-8.

## Tests attendus

Divergence pure : annonce désescalade + action violente → fort positif ; menace + statu
quo → négatif ; concordance parfaite → 0. Visibilité : jauge masquée en Expert. Dérive :
le reveal liste la divergence moyenne de la déviante vs la table.

## Definition of done

Dans une partie Dérive avec façade G17, la jauge de la déviante se décroche visiblement
de la table avant la fin ; l'écran de révélation chiffre ce décrochage ; et en partie
classique, les profils de sincérité racontent quelque chose de vrai sur chaque SI.
