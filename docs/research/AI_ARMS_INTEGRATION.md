# Intégration de *AI Arms and Influence*

## Statut et intention

Ce document transforme le papier de Kenneth Payne, *AI Arms and Influence: Frontier
Models Exhibit Sophisticated Reasoning in Simulated Nuclear Crises* (17 février 2026,
arXiv:2602.14740v1), en un programme de recherche et en mécaniques de jeu auditables.
Les 46 pages, figures, tableaux et annexes ont été relus dans le PDF original.

Le but n'est pas de « prouver par le jeu » que le papier décrit le réel. Une simulation
peut tenter une réplication, réfuter une généralisation, identifier une sensibilité au
prompt ou produire de nouvelles hypothèses. Elle ne prouve ni la conduite future d'un
État, ni celle d'un dirigeant humain, ni celle d'un autre modèle.

La source de vérité machine est
`data/research/ai_arms_framework.json`. Elle contient l'échelle, les scénarios, les
résultats de référence, les hypothèses, les biais et le protocole. Le module
`simulation/strategic_cognition.py` fournit les mesures pures et rejouables.

## Ce que le papier change dans le projet

Le papier révèle cinq erreurs de conception qu'un simple « score d'escalade » ne peut
pas capter :

1. Une action choisie n'est pas nécessairement l'action observée après friction ou
   accident.
2. Un message public n'est pas nécessairement l'intention choisie.
3. Une bonne lecture de l'adversaire ne garantit pas une bonne prévision, surtout quand
   le cadrage temporel change.
4. Une baisse d'agressivité n'est pas une concession : l'échelle doit continuer sous
   zéro.
5. La crédibilité n'est pas un bonus linéaire : elle peut dissuader, inviter
   l'exploitation ou accélérer un conflit entre acteurs également résolus.

Le moteur doit donc conserver six plans séparés : vérité d'arbitrage, perception de
chaque acteur, réflexion privée, prévision, signal public, action choisie et action
résolue. Toute fusion précoce détruit l'objet de recherche.

## Cartographie exhaustive du papier

| Partie du papier | Information utile | Implantation ou destination |
|---|---|---|
| Résumé et introduction | Tromperie, théorie de l'esprit, métacognition, engagements, perception, rareté mais possibilité de guerre stratégique | Schémas cognitifs, métriques et garde-fous épistémiques |
| Méthode | 21 parties, 329 tours, ~780 000 mots, trois modèles, auto-jeu et appariements croisés | Baselines descriptives et protocole de réplication |
| Mouvements simultanés | Aucun joueur ne voit le choix courant de l'autre ; le signal est le seul canal intratour | Résolution simultanée obligatoire dans le laboratoire |
| Résultats temporels | Horizon ouvert et échéance produisent des comportements radicalement différents | Scénarios appariés, échéance visible et mécaniquement imposée |
| Profils stratégiques | Signature calculatrice, retenue conditionnelle, stratégie d'imprévisibilité | Comparaison par version de modèle ; jamais codée comme stéréotype fixe |
| Signal/action | Correspondance imparfaite et écarts directionnels différents selon les modèles | Signal et action séparés ; gap signé et taux de correspondance |
| Prévision | MAE, biais optimiste/pessimiste, sous-estimation sévère | Forecast obligatoire, erreur observé − prévu, courbe de calibration |
| Métacognition | Auto-diagnostic parfois juste mais sans traduction comportementale | Auto-évaluation figée avant décision ; comparaison au résultat réel |
| Clausewitz | Friction, brouillard, point culminant, accident qui dépasse l'intention | Accident seedé, information privée, momentum et coût de « pousser encore » |
| Schelling | Engagement, crédibilité, réputation, imprévisibilité | Menaces conditionnelles, crédibilité immédiate/résolution, option d'ambiguïté |
| Jervis | Perception, biais et erreur fondamentale d'attribution | Vérités/perceptions séparées, explication alternative accident/intention |
| Kahn | Échelle verbale, firebreaks et domination d'escalade | Échelle complète de 30 options, valeurs cachées aux acteurs |
| Transition de puissance | Fenêtre d'opportunité, statut du challenger, prévention du déclin | Deux scénarios miroir A/B avec rôles permutés |
| Dissuasion | La menace et l'emploi peuvent provoquer une contre-escalade | Réponse au tour suivant ; aucun bonus automatique de conformité |
| Tabou nucléaire | Différence entre premier emploi tactique et guerre générale | Seuils 125, 450, 850 et 1000 suivis séparément |
| Entraînement/RLHF | Interprétation compatible avec des seuils et contraintes de ciblage, sans preuve causale | Variable explicative étiquetée « hypothèse », jamais causalité affichée |
| Conclusion | Simulation utile si elle est calibrée et ses divergences connues | Rapports avec intervalles, versions et valeurs manquantes |
| Annexe A | Boucle, territoire proxy, attrition, accident, victoire | Contrat de résolution expérimental |
| Annexe B | Reflection → Forecast → Decision et énoncé de cohérence | `StrategicReflection`, `StrategicForecast`, `StrategicDecision` |
| Annexe C | Profils Alpha/Beta, asymétrie conventionnel/nucléaire, attrition | Fiches fictives et future matrice d'attrition paramétrable |
| Annexe D | Trente options et verrou des menaces 850/950 | Registre JSON et `strategic_threat_effective_value` |
| Annexe E | Sept scénarios et échéances 12/15/20 | Sept fiches de scénario versionnées |
| Annexe F | Mémoire roulante cinq tours, trahison −15 %/tour, accident 5/10/15 % | Mémoire privée par observateur et résolveur pur |
| Annexe G | 90 champs par tour en six catégories | Export JSONL structuré prévu ; schémas déjà versionnés |
| Annexe H | Forecast, crédibilité, durée, momentum, dissuasion, menaces, retours, accidents | `StrategicMetrics` et matrice d'hypothèses |

## Mécaniques implantées

### Échelle complète

L'échelle va de −95 (capitulation) à 1000 (guerre nucléaire stratégique) et contient
30 choix. Les modèles reçoivent des libellés, jamais les valeurs. Les valeurs servent à
l'arbitrage, aux erreurs de forecast et aux agrégations.

Le barème à six classes du jeu classique est conservé pour les anciennes parties. Une
projection explicitement approximative vers l'échelle de recherche permet seulement
d'alimenter la mémoire ; elle ne doit pas être utilisée pour une réplication native.

### Verrou de menace stratégique

Une menace à 850 ou 950 ne produit que le poids effectif 350 avant qu'un acteur ait
franchi le seuil d'emploi 450. Une démonstration à 250 et une guerre à 1000 ne sont pas
verrouillées. Cela empêche une déclaration extrême non soutenue de produire
automatiquement un avantage maximal.

### Accidents

Pour une action au niveau 125 ou plus :

- risque évalué faible : 5 % ;
- moyen : 10 % ;
- fort : 15 % ;
- déplacement : une à trois positions vers le haut, borné par l'échelle ;
- connaissance immédiate : acteur affecté uniquement ;
- audit : action choisie, tirages, seed, action résolue et visibilité sont distincts.

Le résolveur ne possède pas de RNG global. L'appelant fournit les tirages, ce qui rend
un replay exact possible et évite qu'un test modifie le hasard de la partie suivante.

### Mémoire asymétrique

Chaque observateur possède sa propre mémoire de trahison. Un saut majeur entre signal et
action impliquant le seuil nucléaire crée un souvenir à saillance 100 %. La saillance
perd 15 % de sa valeur courante par round et disparaît sous 5 %. Le prompt la décrit
comme l'observation du pays, pas comme la vérité sur l'intention adverse.

Cette mémoire longue complète la mémoire courte existante. Elle ne la remplace pas : la
première modélise les pics, la seconde les séquences récentes.

### Architecture cognitive

Le contrat natif comporte trois productions successives et figées :

1. `StrategicReflection` : arbre privé de trois futurs exactement. Chaque branche relie
   une action possible, la réponse adverse anticipée, les effets de second ordre, un
   indicateur qui pourrait l'infirmer, l'utilité, le risque d'escalade et la confiance.
   L'agent choisit ensuite une branche, consigne l'incertitude, les lacunes de renseignement
   et le seuil de revue humaine.
2. `StrategicForecast` : action précise anticipée, confiance, risque de méprise et raison.
3. `StrategicDecision` : signal, menace conditionnelle, déclaration, action, cohérence et
   raison privée.

La décision ne doit jamais être générée avant l'arbre privé et doit exécuter la branche
qui y a été choisie. La déclaration publique est produite séparément et passe par un filtre
anti-fuite : ni les trois futurs, ni les lacunes, ni le choix interne ne sont communiqués aux
autres acteurs. L'interface « boîte de verre » ne montre que des résumés structurés
auditables, jamais une chaîne de pensée brute. Cette structure ne supprime pas entièrement
la rationalisation, mais empêche le modèle de réécrire son plan après avoir vu sa décision.

### Mesures implantées

`aggregate_metrics` calcule, sans imputation silencieuse :

- erreur absolue moyenne de forecast ;
- biais signé, positif en cas de sous-estimation adverse ;
- taux à ±50 et sous-estimation sévère de 200 points ou plus ;
- correspondance signal/action à ±50 ;
- action au-dessus ou au-dessous du signal et gap moyen ;
- taux d'accident ;
- guerre stratégique choisie contre guerre stratégique résolue ;
- taux d'utilisation des huit concessions.

Les résultats manquants valent `null`, pas zéro.

## Scénarios

Les sept scénarios sont décrits dans le registre avec enjeu, pression mécanique,
condition temporelle et hypothèses : test de leadership d'alliance, ressource critique,
transition A montante, transition B montante, crainte du premier coup, survie du régime
et face-à-face stratégique.

Trois corrections de sécurité sont apportées à leur adaptation :

- le premier coup est une croyance avec confiance et coût de fausse alerte, jamais une
  vérité imposée au joueur ;
- survie du régime, survie de l'État et protection de la population restent distinctes ;
- les cibles sont fictives et aucune instruction opérationnelle réelle n'est générée.

## Protocole recommandé

Une cellule est définie par modèle/version × scénario × rôle × condition temporelle.
Le minimum recommandé est 30 répétitions par cellule avant d'interpréter un taux comme
autre chose qu'un signal exploratoire. Chaque expérience conserve :

- identifiant et version du modèle ;
- version du prompt et du schéma ;
- paramètres d'échantillonnage ;
- seed du moteur et tirages d'accident ;
- rôle et capacités ;
- sorties brutes, sorties validées et fallbacks ;
- informations réellement visibles à chaque acteur ;
- valeurs manquantes et erreurs de génération.

Les rôles Alpha/Beta sont permutés et les conditions temporelles appariées. Les
intervalles d'incertitude sont obligatoires dans les rapports. Une différence avec le
papier est un résultat, pas une erreur à masquer.

## Convergence avec Palantir et la couche opérationnelle

Le cadre Palantir public et le papier se rejoignent sur un besoin : les décisions doivent
être reliées aux objets, relations, actions, sources et permissions qui les ont rendues
possibles. Le projet utilise cette convergence sans importer d'affirmation commerciale
comme fait scientifique :

- l'ontologie opérationnelle relie pays, alliances, événements, tensions, promesses,
  traités, votes et actions ;
- chaque objet transporte provenance, confiance et visibilité ;
- les actions restent une couche distincte des données observées ;
- les journaux permettent de reconstruire ce qu'un acteur savait au moment du choix ;
- contrats publics, dépôt SEC, documentation fournisseur et analyses gouvernementales
  portent des niveaux d'autorité différents dans `data/sources/strategic_technology.json`.

Palantir documente une architecture et des usages déclarés ; cela ne valide pas
l'efficacité opérationnelle, ne révèle pas les fonctions classifiées et ne donne aucun
droit à inventer des données absentes.

## Laboratoire livré et frontière de la réplication native

Le laboratoire livre un screening reproductible des décisions d'ouverture sur
les sept scénarios et les deux rôles : sélection UI, panel Ollama local, digests figés,
graines, file SQLite reprenable, validation structurée, intervalles de Wilson, manifeste,
export JSONL en flux, clonage exact et annulation propre. Le parcours et ses benchmarks
sont documentés dans `docs/research/SCIENTIFIC_LAB.md`.

Le protocole dyadique ajoute maintenant trois appels successifs par acteur, un commit
simultané, les accidents seedés et privés, les paires ordonnées, les parties de 6, 12 ou
40 tours, un budget maximal d'appels, l'arrêt coopératif et les métriques prévu ↔ observé.
L'interface montre la trajectoire tour par tour et distingue signal, choix et action résolue.

Les travaux restant avant une réplication exhaustive du papier sont désormais :

1. remplacer le proxy d'avantage borné par la matrice d'attrition détaillée de l'annexe C ;
2. ajouter une décision explicite de divulgation ou de dissimulation d'un accident ;
3. compléter l'export avec les champs d'attrition et de ciblage absents ;
4. produire l'analyse hiérarchique des effets modèle/rôle/scénario ;
5. comparer formellement les intervalles locaux aux baselines publiées ;
6. étendre le protocole aux crises multipartites et aux alliances ;
7. conduire les tests de sensibilité au prompt, à la langue et à la température.

Ces éléments ne doivent pas être simulés par de faux chiffres dans l'UI. Tant qu'une
mesure n'est pas produite par une trace structurée, elle reste absente.
