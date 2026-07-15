# Spec G24 — Marché V2 : scoring de forecaster + liquidité honnête

> Livrable Cowork (2026-07-15). Sources vérifiées 25/25 (2ᵉ passe de recherche) :
> Hanson (mktscore), Othman/Pennock/Reeves/Sandholm (TEAC + GHPM), FAQ scores
> Metaculus, Maniswap/Manifold. Détail : `docs/RECHERCHE_FONCTIONNALITES_2.md`.

## Diagnostic

Notre LMSR est le bon mécanisme (validé : il fonctionne dès 1 parieur, l'argent fictif
est le choix canonique, le budget de banque est borné par b·ln(n)). Trois manques :
le paramètre b est fixé à la main (le piège documenté du domaine — GHPM l'a regretté),
le score d'un parieur se réduit à son PnL (illisible entre parties, sniffable en fin de
partie), et rien ne récompense l'engagement précoce ni ne protège l'indépendance des
prédictions.

## Principe (trois briques indépendantes)

### 1. Liquidité honnête

- Remplacer le b constant par le market maker **liquidity-sensitive** d'Othman/Sandholm :
  `b(q) = α·Σqᵢ`, avec `α = v/(n·log n)` et `v = 0,05` (commission effective 5 %) en
  point de départ documenté. Les prix se raidissent avec le volume : un gros pari tard
  ne retourne plus le marché comme au premier round.
- Conserver le LMSR actuel derrière un flag de config (comparaison A/B en playtest) ;
  la banque de la partie reste dimensionnée par la borne b·ln(n_issues).

### 2. Scores de forecaster (façon Metaculus)

- **Baseline score** par joueur et par marché : log score rescalé contre le prior
  « chance » (0 = prédiction naïve, +100 = parfaite en binaire). Fonctionne même seul.
- **Peer score** : 100 × (log score du joueur − moyenne des autres), somme nulle par
  marché — LE classement de table propre à 2-10 parieurs.
- **Coverage** : fraction de la durée du marché pendant laquelle le joueur avait une
  position ; les leaderboards classent par Σ Peer / Σ coverage avec un plancher de
  coverage (anti-sniping : parier une seconde avant la résolution ne rapporte rien).
- Affichage : sur la page marché (score par marché) et au bilan de fin (score de
  forecaster de la partie, à côté des LP) ; agrégat au profil (calibration à terme).

### 3. Période cachée & engagement précoce

- Les **k premiers rounds** (config, défaut : 1er tiers de l'horizon), la cote
  communautaire est **masquée** : chacun parie à l'aveugle sur sa propre lecture (les
  positions restent visibles pour soi). Révélation ensuite — moment théâtral en soi.
- **Bonus d'activité** : petite dotation additionnelle par partie jouée (pattern GHPM :
  c'est le bonus récurrent qui fait la liquidité, 39 % des tickets), plafonnée pour ne
  pas gonfler l'inflation de monnaie fictive.

## Surface joueur (règle « 12-65 ans » — docs/PRINCIPE_SIMPLICITE.md)

Tout ce qui précède est du MOTEUR. Ce que le joueur voit :

- Sur la page marché : la cote (« 62 % »), un bouton Parier, son solde. Rien d'autre
  ne change.
- Pendant la période cachée : « Parie ton intuition — la cote de la table se révèle au
  round k. » (C'est une simplification vécue, pas une complexité.)
- Au bilan : UNE ligne — « Score de prophète : 73/100 · 1er de la table » — avec une
  bulle « ? » qui explique en une phrase (« plus tu devines juste et tôt, plus il
  monte »). Baseline/Peer/coverage n'apparaissent JAMAIS en surface : ce sont les
  ingrédients du chiffre, consultables dans l'onglet Informations pour les curieux.

## Répartition

- **Cowork** : cette spec ; choix des libellés (« score de prophète » ?) ; calibration
  v/α et durée de période cachée sur 10 parties ; relecture du bilan affiché.
- **Claude Code (CC-14, 1-2 sessions)** : brique 1 dans `market/` (fonction de coût
  OPRS + flag), brique 2 (scores purs testés + persistance + affichages), brique 3
  (masquage par config + bonus). Chaque brique est livrable séparément.

## Tests attendus

OPRS : somme des prix ∈ [1, 1+α·n·log n] ; prix se raidissent avec Σq ; flag → LMSR
inchangé. Scores : baseline naïf = 0 ; peer somme nulle par marché ; coverage bornée
[0,1] avec plancher au leaderboard. Période cachée : cote non exposée par l'API avant
le round k (pas seulement masquée à l'UI) ; bonus versé une fois par partie.

## Definition of done

Sur une table de 3 parieurs, le classement Peer/coverage désigne le meilleur prophète
même quand tous finissent positifs ; un pari massif au dernier round ne retourne plus
la cote ; et pendant la période cachée, deux joueurs qui parient différemment ne se
voient pas — la révélation de la cote fait un « oooh ».
