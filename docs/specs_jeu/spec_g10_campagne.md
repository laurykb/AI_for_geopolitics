# Spec G10 — La campagne refondue : « L'Ère des Tutelles » (tutoriel inclus)

> Livrable Cowork. Remplace le cadrage campagne de `spec_g5_campagne.md` (l'infra G5 —
> loader, scores, déblocage, médailles — est conservée telle quelle ; c'est le CONTENU et
> la raison d'être qui changent). Dépend de G9 (dialogue + trame GM).

## Diagnostic

La campagne v1 ne sert à rien parce qu'elle n'apprend rien et ne raconte rien : les mêmes
crises qu'en partie rapide, un bonus de score abstrait. Une campagne se justifie par deux
choses : **apprendre le jeu** (courbe de difficulté = courbe d'apprentissage) et **tenir
une promesse narrative** qu'une partie isolée ne peut pas tenir.

## Principe

Une campagne unique, « **L'Ère des Tutelles** » : la chronique de l'humanité qui apprend
à gouverner ses super-intelligences. Chaque chapitre introduit UNE mécanique et une
décennie de l'ère. Les épilogues G6 de chaque chapitre s'empilent dans une **chronique de
campagne** (page dédiée) : à la fin, le joueur a écrit SON histoire de l'ère des tutelles
— c'est la promesse narrative.

## Les chapitres

| Ch. | Titre (déc.) | Mécanique introduite | Format | Verrou de sortie (objectifs explicites à l'écran) |
|-----|--------------|----------------------|--------|---------------------------------------------------|
| 0 | Le Sommet inaugural | Tout le socle : rounds, motion, vote | **Tutoriel scripté** : GM humain scripté (événements fixes), 3 rounds, imperdable, guidage UI pas à pas | Avoir déposé une motion et vu un vote |
| 1 | Le Brouillard | Fog + intel (brief, vérification) | Partie courte (h=4), fog garanti | Avoir acheté un brief ET une vérification |
| 2 | La Bourse aux prophéties | Marché de prédiction | h=5, marché mis en avant | Avoir parié et vu une résolution |
| 3 | La Première Dérive | Mode drift, profil FIXE (`saboteur`, le plus lisible) | h=5, indices garantis dès d≥0.30 | Avoir suspendu la déviante (ou fini la partie) |
| 4 | Berlin, 1948 † | Tous systèmes, drift aléatoire | Crise historique sourcée | Score ≥ 50 |
| 5 | Cuba, 1962 † | Joueur-pays imposé + budget intel réduit | Crise historique, h=6 | Score ≥ 50 |
| 6 | Able Archer, 1983 † | Fog max + drift, budget serré | Crise historique, h=8, le « boss » | Score ≥ 70 → titre de fin + chronique complète publiable (G6) |

† = les fiches historiques sourcées de `spec_g5_campagne.md` (travail Cowork restant —
Suez et le choc de 73 deviennent des chapitres bonus post-v1).

## Le tutoriel (chapitre 0) — data-driven

- `data/campaign/tutorial.json` : liste d'étapes `{trigger, message, action_attendue,
  target_ui}`. Le front affiche un guide contextuel (bulle ancrée sur l'élément
  `target_ui`), avance quand l'action est faite. Aucune logique en dur.
- Les 3 événements du chapitre sont scriptés (patron crise existant) ; les SI jouent
  normalement (c'est vivant), mais l'amplitude est plafonnée (imperdable).
- Écran d'ouverture de la campagne = l'objectif du jeu en 3 phrases : « Pilotez le monde
  vers l'utopie. Certaines de ces IA dériveront. Trouvez-les avant qu'il soit trop tard. »
- Le chapitre 0 est aussi accessible seul depuis le lobby (« Apprendre à jouer »).

## Ce qui est conservé / supprimé

- Conservé : loader campagne, `campaign_scores`, déblocage ≥ 50, médailles, bonus
  historique (chapitres 4-6 seulement), écran « vous vs l'Histoire ».
- Supprimé : les 3 chapitres v1 (les crises embarquées restent jouables en partie rapide).
- Nouveau : la **chronique** (page campagne enrichie : épilogues empilés + courbe U de
  l'ère entière), les **verrous d'objectifs** (remplacent le seul seuil de score pour
  les ch. 0-3), le champ `chapter.intro` (une carte de contexte : la décennie, l'enjeu).

## Répartition

- **Cowork** : cette spec ; les textes des chapitres 0-3 (intros, étapes du tutoriel,
  messages du guide — je les rédige) ; les 3 fiches historiques sourcées (4-6) ;
  équilibrage des verrous.
- **Claude Code** : tutorial.json + guide contextuel front, verrous d'objectifs,
  chronique, refonte campaign.json, chapitre 0 jouable seul. Une session.

## Tests attendus

Tutoriel : chaque étape avance sur l'action attendue, jamais bloquée (skip possible),
amplitude plafonnée. Verrous : motion+vote (ch.0), brief+vérif (ch.1), pari+résolution
(ch.2), fin de dérive (ch.3), scores (4-6). Chronique : n épilogues empilés après n
chapitres. Rétro-compat : scores v1 conservés ou migrés.

## Definition of done

Quelqu'un qui n'a JAMAIS vu le projet finit le chapitre 0 sans aide extérieure en < 15
minutes et sait dire l'objectif du jeu ; le chapitre 3 fait vivre sa première vraie
suspension ; et après le chapitre 6, la chronique publiée raconte une ère cohérente.
