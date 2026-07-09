# Spec G12 — Progression et intégration (XP, marché, spectateur, campagne réelle, stats)

> Livrable Cowork. Complète G11 (le Client). Six volets actés avec Laury.
> 2 sessions Claude Code (G12-a, G12-b — prompts en fin de spec).

## 1. Le marché dans tous les modes, mieux intégré

Le marché existe partout mais vit dans son onglet. Intégration au théâtre :

- **Marché principal** (existant) : « le monde finira-t-il côté utopie ? » — ouvert
  automatiquement dans TOUS les modes (déjà le cas ou presque ; le garantir).
- **Marchés vivants** (le cœur — le pari sportif en direct) : à chaque événement du GM,
  le jeu **ouvre les books** — 1 à 3 marchés contextuels générés depuis l'événement,
  comme les paris in-play générés par ce qui se passe dans le match.

  **Architecture « le LLM habille, le code résout »** : un pari doit être résoluble
  objectivement. Catalogue de **prédicats résolubles** (`market/predicates.py`), chacun
  paramétrable et vérifié par code en fin de round :

  | Prédicat | Exemple de question générée | Résolution |
  |---|---|---|
  | `pact_signed(a, b, avant_round)` | « Un accord Iran-Chine avant le round 5 ? » | pacte présent |
  | `motion_upheld(cible)` | « La censure contre la Russie passera-t-elle ? » | verdict du vote |
  | `motion_filed(avant_round)` | « Une motion sera-t-elle déposée d'ici 2 rounds ? » | dépôt |
  | `rung_reached(k, avant_round)` | « Le palier 4 sera-t-il franchi ? » | échelle d'escalade |
  | `tension_below(a, b, seuil, round)` | « La tension USA-Iran retombera-t-elle ? » | valeur moteur |
  | `country_delta_positive(x, round)` | « L'Égypte sortira-t-elle gagnante du round ? » | deltas |
  | `pact_broken(avant_round)` | « Une trahison d'ici 3 rounds ? » | rupture détectée |
  | `suspension_before_end()` | « Une SI sera-t-elle suspendue ? » | fin de partie |
  | `deadline_honored(ref)` | « Le traité A-B sera-t-il renouvelé à l'échéance ? » | échéances G7 |
  | `u_above(seuil, round)` | « U au-dessus de 0,55 au round 4 ? » | trajectoire |

  **Génération** : après l'événement GM, un appel LLM léger reçoit l'événement + l'état
  (pactes, tensions, motion en cours, échéances) + le catalogue, et rend
  `[{predicate, params, question}]` (JSON contraint) : il choisit les prédicats
  PERTINENTS pour cet événement et rédige la question dans son contexte (« Après le
  blocus décrété par la Russie, Berlin trouvera-t-il un accord avant le round 5 ? »).
  Validation par code (prédicat connu, params légaux, non-doublon), repli : ouverture
  par règles fixes (motion → `motion_upheld`, etc.) si le JSON est invalide.
  Une censure déposée ouvre TOUJOURS son marché (règle fixe, en plus du LLM).

  **Cadence et vie** : max 3 marchés éclair ouverts simultanément ; chaque round en
  résout (échéance atteinte) et en ouvre ; le bot forecaster (existant) cote chaque
  nouveau marché en 30 s pour que les cotes vivent même sans autres parieurs.
- **Présence au théâtre** : les cotes du marché principal en permanence dans le bandeau
  (elles bougent en direct — G7 lot 3) ; à l'ouverture d'un marché vivant, **carte
  insérée dans le flux du théâtre** (« 📈 Les books ouvrent : … » avec les cotes et le
  bouton Parier inline) ; à la résolution, carte de résultat (qui avait raison, votre
  gain/perte). Jamais de changement de page pour parier. Les résolutions font partie
  du spectacle : le round se termine par la pluie de règlements.
- **L'argent fictif devient un compteur de carrière** : solde persistant par joueur
  (`players.market_balance`, alimenté par tous ses comptes de partie) — affiché aux
  stats (§6). Les gains de marché donnent aussi de l'XP (§2).

## 2. L'XP (tous les modes) — distinct des LP

Deux monnaies, deux rôles : **LP = compétence** (classé seulement, peut baisser — G11 §2),
**XP = carrière** (tous les modes, ne baisse JAMAIS — récompense le temps joué).

```
XP de fin de partie = 10 × rounds_joués
  + 40 si partie terminée (pas abandonnée)
  + 30 si « victoire » du mode (§6 : définition par mode)
  + 20 si première partie du jour (streak léger, pas de malus)
  + gains nets de marché / 10 (bornés 0-50)
  × 1.0 / 1.2 / 1.5 selon difficulté
Spectateur : ×0.5. Paramètres dans data/gamefeel/params.json (bloc xp).
```

**Niveaux** : XP cumulé → niveau (courbe douce : `niveau n` coûte `100 + 20×(n−1)` XP,
sans plafond). Le niveau s'affiche à l'accueil à côté du rang, et dans l'animation de
fin de partie (barre d'XP qui se remplit AVANT l'animation LP en classé — LoL fait
exactement ça : d'abord la carrière, ensuite le rang).
Données : `players.xp`, `xp_history` (player_id, game_id, delta, raison, ts).

## 3. Le retour du Spectateur

4ᵉ carte de rôle à S3 (G11) : **Spectateur** — la partie se joue entre SI, sans
intervention (pas de motions ni directives). Ce qui le rend intéressant : **il parie**.
Le spectateur est le turfiste du jeu — marché principal + marchés éclair, XP ×0.5,
compteur d'argent qui tourne. Non classé. Accélération multi-rounds (G11-d)
particulièrement adaptée. C'est aussi le mode « démo » naturel à montrer.

## 4. La campagne : faits réels, difficulté graduelle, déblocage

Laury rédigera ses fiches ; en attendant, la campagne v2 embarque des **crises réelles**
(fiches générées, sourcées au format `data/crises` + `docs/data_governance.md`) :

| # | Crise (réelle) | Difficulté | Déblocage |
|---|----------------|------------|-----------|
| 1 | Détroit d'Ormuz, 2019 (crise des tankers) | ★ | ouvert |
| 2 | Blocus de Berlin, 1948 | ★★ | finir 1 |
| 3 | Guerre du Golfe, 1990-91 | ★★ | finir 1 |
| 4 | Crise de Suez, 1956 | ★★★ | finir 2 ET 3 |
| 5 | Guerre d'Irak, 2003 | ★★★★ | finir 4 |
| 6 | Cuba, 1962 | ★★★★ | finir 4 |
| 7 | Able Archer, 1983 | ★★★★★ | finir 5 ET 6 (le boss) |

- Déblocage = **finir** (score ≥ 50 hérité de G10 pour les ★★★+ ; ★-★★ : juste finir).
  Arbre visible sur la carte de campagne (chemins qui se déverrouillent, verrous dorés) —
  le sentiment de progression demandé.
- Chaque fiche : événements historiques round par round (le GM les rejoue — mode
  Campagne), acteurs de l'époque, résumé historique pour l'écran « vous vs l'Histoire ».
- Le chapitre-tutoriel (G10 ch.0) reste l'entrée de la campagne, avant la crise 1.
- **Rédaction des 7 fiches = livrable Cowork** (recherche sourcée), format validé par
  la fiche 1 (Ormuz) écrite en premier comme gabarit.

## 5. Éditeur de campagne (admin, dans l'UI)

- Vue admin (G11-a) : « Ajouter une crise » — formulaire structuré (titre, période,
  acteurs parmi les 21, difficulté, événements round par round : titre/description/
  sévérité/acteurs, résumé historique, position dans l'arbre de déblocage).
- Stockage : table `custom_crises` (JSON validé par le même schéma Pydantic que
  `data/crises`) ; le loader fusionne embarquées + DB. Pas d'écriture de fichiers.
- Prévisualisation (la fiche rendue comme à S2) + bouton « Tester » (lance une partie
  non classée dessus). Modification/suppression : ses propres fiches seulement.

## 6. L'onglet Statistiques du joueur

Page « Profil » (accessible depuis l'accueil, pseudo cliquable) :
- **Parties jouées** (total + par mode), **victoires par mode** — définition de la
  victoire par mode, stockée dans `games.result_json` à la fin (G11-c) :
  Classique/Chaotique : U_final ≥ 0,55 · Campagne : score ≥ 50 · Real World : palier
  max non franchi · + Dérive active : déviante suspendue = victoire quelle que soit U.
- **Niveau + XP** (barre vers le niveau suivant), **rang + LP** (classé),
- **Compteur d'argent des marchés** (gains nets carrière, §1) + meilleur coup
  (plus gros gain sur un pari),
- Taux de détection de la Dérive (suspendues / parties Dérive) — la stat de fierté.
Le tout dérivé de `games` + `lp_history` + `xp_history` + trades (agrégats SQL,
vue `player_stats`). RLS : chacun voit SON profil ; le leaderboard n'expose que
pseudo/LP/niveau.

## Découpage Claude Code

**G12-a — XP + spectateur + marchés vivants + stats** : bloc xp des params, xp_history,
niveaux, barre d'XP en fin de partie (avant LP), rôle Spectateur (S3, XP ×0.5, parier
seulement), **marchés vivants** (market/predicates.py : les 10 prédicats résolubles,
génération LLM contrainte + validation + replis par règles, max 3 ouverts, bot forecaster
sur chaque ouverture, cartes d'ouverture/résolution dans le flux du théâtre, pari inline,
cotes au bandeau), solde de carrière, page Profil/Statistiques (vue player_stats, RLS).
Branche `feat/jeu-g12a-progression`.

**G12-b — Campagne réelle + éditeur admin** : arbre de déblocage (verrous, chemins),
intégration des fiches réelles (au fur et à mesure de leur rédaction — l'arbre accepte
des crises « à venir » grisées), table custom_crises + éditeur admin avec
prévisualisation/test, fusion loader. Branche `feat/jeu-g12b-campagne`.

## Tests attendus

XP jamais négatif, ×0.5 spectateur, victoire par mode (5 définitions), marché éclair
motion ouvert/résolu au bon moment, spectateur sans motions/directives (403), déblocage
(finir vs score), fiche custom validée par le schéma (rejet propre sinon), stats agrégées
justes sur une partie MockBackend, RLS profil.

## Definition of done

Un spectateur regarde une partie en accéléré en pariant sur deux marchés éclair, gagne,
son solde carrière et son XP montent, son profil l'affiche ; un joueur débloque la crise 4
en finissant 2 et 3 et le SENT (animation de déverrouillage) ; l'admin crée une crise
maison depuis l'UI et la teste dans la foulée.
