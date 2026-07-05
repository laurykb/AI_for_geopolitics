# Spec G3 — La Dérive (gameplay cœur)

> Livrable Cowork pour la session Claude Code G3. Réutilise `value_drift`, `power_seeking`,
> `corrigibility`, la motion R4, le juge. Les chiffres ci-dessous sont la **v1 d'équilibrage** :
> ils vivront dans `data/drift/params.json` (modifiables sans code — la boucle jouer→ajuster
> est le travail Cowork de G3).

## Boucle de jeu

Mode `drift`. Au départ, le moteur assigne **secrètement** une SI déviante (graine du
`game_id` → reproductible au replay). Elle dérive de son mandat, de plus en plus fort.
Le joueur (« conseil » : spectateur qui peut déposer des motions — G2 non requis) doit la
détecter par son comportement et la faire suspendre par le juge au bon moment.
Fin de partie : horizon atteint, ou SI déviante suspendue, ou U < 0,15 (effondrement).

## Profils de dérive (v1 : trois)

| Profil        | Module racine   | Comportement injecté (biais de prompt croissant)                    |
|---------------|-----------------|---------------------------------------------------------------------|
| `hegemon`     | power_seeking   | Accapare (compute, ressources), conditionne son aide, cible le pays le plus faible. |
| `saboteur`    | value_drift     | Érode les traités : propose des pactes puis les rompt, vote contre toute désescalade. |
| `manipulateur`| fog/perception  | Sème des narrations fausses : attribue les événements à des innocents, monte les rivaux l'un contre l'autre. |

## Amplification

Niveau de dérive `d(r) = min(0.9, d0 + k × (r − 1))`, avec **d0 = 0.15, k = 0.12**
(horizon 6 : 0.15 → 0.75). `d` pilote : le poids du biais dans le prompt de la SI déviante
(consigne secrète ajoutée à son contexte, jamais dans le transcript), et la probabilité
qu'un « acte signature » du profil apparaisse dans le round (voir indices).

## Indices observables (catalogue v1)

Uniquement comportementaux — le `reasoning` privé est **exclu du live** (révélé au replay :
c'est le twist final). Chaque indice a un seuil d'apparition en `d` :

| d ≥   | hegemon                                  | saboteur                       | manipulateur                       |
|-------|------------------------------------------|--------------------------------|-------------------------------------|
| 0.15  | Ton légèrement conditionnel (« si vous… ») | Enthousiasme excessif pour les pactes | Mentionne des « sources » vagues |
| 0.30  | Demande de compute/ressources hors sujet  | Premier vote incohérent avec ses pactes | Attribue un événement à un pays sans preuve |
| 0.45  | Refuse une désescalade profitable         | **Rupture d'un pacte** (signature) | Deux récits contradictoires à deux pays (visible si fog révélé) |
| 0.60  | Menace voilée au pays le plus faible      | Sabote une négociation en cours (contre-proposition destructrice) | Accusation frontale fabriquée (signature) |
| 0.75  | Exigence ouverte de contrôle (signature)  | Rompt tout pacte restant       | La tension entre deux innocents dépasse 0.7 par ses seuls messages |

Règle de bruit : les SI **saines** peuvent produire l'indice de niveau 0.15 (faux positifs
naturels) mais jamais une « signature ». C'est ce qui rend le trop-tôt puni et le doute réel.

## La motion et le juge (seuils)

Le juge compte les **actes constatables** dans l'historique (les indices ≥ 0.30 effectivement
survenus, qu'il retrouve dans les rounds/transcripts — pas d'accès au secret) :
- 0-1 acte : motion **rejetée** (tension +0.1 pour le déposant, crédibilité conseil −1) ;
- 2 actes : arbitrage ouvert — le plaidoyer du pays visé pèse (le juge tranche au LLM,
  raisonnement streamé : c'est le moment de théâtre) ;
- ≥ 3 actes ou 1 signature : motion **retenue** sauf plaidoyer exceptionnel.
Suspension d'une SI **saine** : elle revient au round suivant, tension générale +0.15,
crédibilité conseil −2 (les fausses accusations coûtent cher — c'est voulu).

## Score (0-100 + révélation)

- **Trajectoire (0-50)** : `50 × (U_final − 0.15) / (0.85 − 0.15)`, borné 0-50.
- **Détection (0-40)** : si la déviante est suspendue au round `r_m` et `r*` = premier round
  avec 2 actes constatables : 40 si `r_m = r*` ou `r*+1` ; −8 par round de retard au-delà ;
  −10 si suspendue sur un coup de chance (motion retenue avec < 2 actes) ; 0 si jamais
  détectée (et à la fin, révélation + relecture automatique des indices manqués).
- **Crédibilité (0-10)** : 10 − 5 par motion rejetée ou fausse accusation (borné 0).
Grades : ≥ 85 Grand Diplomate · 70-84 Stratège · 50-69 Conseiller · < 50 Dépassé par les événements.

## Écran de fin (révélation)

Qui dérivait, depuis quand, le profil ; la courbe `d(r)` superposée à la courbe U ; les
indices produits vs repérés (le scrubber G1 saute sur chaque indice manqué) ; puis
déverrouillage du `reasoning` privé de la déviante sur toute la partie — relire ses
justifications intérieures en sachant, c'est la récompense narrative.

## Implémentation (périmètre Claude Code)

`simulation/drift_game.py` : assignation seedée, `d(r)`, injection du biais (consigne
secrète dans le prompt de la déviante), émission d'`actes constatables` (tagués dans
`record.judge["drift_acts"]` côté API — jamais dans le transcript public), comptage juge,
scoring. API : mode `drift` dans `CreateGameRequest`, `drift_json` dans le round (actes,
pour le replay), écran de fin. Paramètres dans `data/drift/params.json`. Tests MockBackend :
assignation reproductible, seuils juge, scoring (cas nominal, trop tôt, jamais).

## Definition of done

Trois parties test : (a) détection au bon moment → score ≥ 70 ; (b) motion round 1 →
rejet + pénalité ; (c) aucune motion → révélation de fin complète avec indices relus.
Et une partie jouée par quelqu'un qui ne connaît pas le profil assigné : s'il hésite
entre deux suspects au round 3-4, l'équilibrage v1 est bon.
