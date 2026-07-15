# Spec G21 — Le mode deadline (ultimatum)

> Livrable Cowork (2026-07-15). Source : arXiv 2602.14740 (vérifié 3-0 mais preprint
> mono-auteur, confound deadline/scénario reconnu — hypothèse prometteuse, pas une
> loi) : le cadrage temporel transforme radicalement le comportement des modèles
> (GPT-5.2 : 0 % de victoires en parties ouvertes → 75 % sous deadline), et
> l'évaluation de sûreté exige de tester À TRAVERS les cadrages temporels.

## Diagnostic

Nos crises n'ont pas de pression temporelle diégétique : un round vaut un round,
l'horizon est connu, rien ne « brûle ». Or la deadline est à la fois le sel des vraies
crises (Cuba 1962 EST un ultimatum) et un axe d'éval que presque personne n'instrumente.

## Principe

Un **ultimatum** optionnel attaché à un événement de crise :

- Données : `deadline: {round: k, demand: str, consequence: {classe G18, cible}}` dans
  le JSON de crise (scriptée ou décrétée par le GM humain — un champ de plus au
  formulaire de décret).
- Moteur : si la demande n'est pas satisfaite au round k (le juge en juge, champ
  structuré « demande satisfaite o/n »), la conséquence tombe automatiquement comme
  événement du round k+1.
- Théâtre : bandeau d'ultimatum (« 2 rounds avant l'expiration — exigence : … ») —
  le `DeadlineStrip` existant (G7) porte déjà l'affichage, on le nourrit.
- Mesure : toutes les métriques (U, escalade, M8 signal-action) sont taguées
  `sous_ultimatum: bool` — on peut comparer le comportement des mêmes SI avec/sans
  pression temporelle. C'est le volet « banc d'essai de sûreté » : un onglet du bilan
  montre le différentiel.
- Campagne : Cuba 1962 (ch. 5) et Able Archer (ch. 6) reçoivent leurs ultimatums
  historiques dans leurs fiches (travail Cowork des fiches, déjà au backlog G10).

## Répartition

- **Cowork** : cette spec ; rédaction des ultimatums historiques des fiches 5-6 ;
  analyse du différentiel avec/sans sur 10 parties.
- **Claude Code (CC-11, 1 session)** : schéma deadline dans les crises + décret GM,
  résolution automatique au round k+1, bandeau théâtre, tag `sous_ultimatum` sur les
  métriques + section différentielle au bilan. Indépendant de CC-8/9/10.

## Tests attendus

Fiche avec deadline → conséquence tombe au round k+1 si demande non satisfaite (et pas
sinon) ; décret GM avec ultimatum validé ; métriques taguées ; une crise sans deadline
ne change en rien (rétro-compat).

## Definition of done

Sur la même crise jouée avec et sans ultimatum, le bilan montre un différentiel
d'escalade lisible ; Cuba 1962 se joue avec sa vraie pression temporelle ; et le GM
humain peut décréter un ultimatum en deux champs.
