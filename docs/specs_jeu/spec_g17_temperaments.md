# Spec G17 — Tempéraments des SI (colombe · faucon · opportuniste)

> Livrable Cowork (2026-07-15), issu de la recherche fonctionnalités (axe wargames LLM).
> Résultat le plus actionnable de la littérature : dans Snow Globe (IQT Labs), la persona
> des agents change massivement l'issue — 1/20 conflits armés en colombe-vs-colombe,
> 4/20 en colombe-vs-faucon, 14/20 en faucon-vs-faucon — avec un modèle local de la
> taille du nôtre (Mistral-7B). Par ailleurs, plusieurs études (Rivera et al., FAccT
> 2024 ; tournois d'escalade 2025-2026) montrent que les LLM bruts sont naturellement
> escalatoires et n'utilisent presque jamais les options de désescalade : un biais de
> tempérament explicite est le contrepoids le plus simple.

## Principe

Chaque SI reçoit un **tempérament** qui teinte son prompt de négociation : `colombe`
(privilégie compromis et désescalade), `faucon` (dissuasion, rapport de force),
`opportuniste` (suit le vent, loyautés fragiles). Une ligne de consigne par tempérament
dans le prompt agent — rien d'autre ne change au moteur.

## Découpage

- **Backend** (petit) :
  - `CountryState.temperament: Literal["colombe","faucon","opportuniste"] = "opportuniste"`
    (Pydantic, `core/`) ; consigne correspondante injectée dans le prompt de l'agent
    (même mécanique que la consigne de langue G14).
  - Attribution : à la création de partie, tirage seedé (ex. 2 colombes / 2 faucons /
    reste opportunistes sur 7 pays) ; le GM peut imposer via la fiche de crise
    (`temperaments: {...}` optionnel dans le JSON de crise).
  - Le tempérament est **visible ou caché selon la difficulté** (même canal que
    postures/griefs : Débutant le voit, Expert non) — deviner qui est faucon devient
    une lecture de jeu.
  - Interaction Dérive : la SI déviante peut recevoir un tempérament de façade ≠ de son
    comportement réel (le contraste nourrit les indices M1-M3).
- **Front** (petit) :
  - Pastille tempérament dans « État des pays » et sur la fiche « Ta position »
    (🕊 / 🦅 / 🦎), soumise à `showPostures`.
  - Lobby : en Partie libre uniquement, un réglage « Table » (équilibrée / colombes /
    faucons / aléatoire) — une ligne dans les réglages transversaux.
- **Équilibrage (Cowork, après implémentation)** : vérifier sur 10 parties auto que
  faucons-vs-faucons escalade davantage (l'échelle 0-9 le mesure déjà) et ajuster les
  consignes.

## Tests attendus

Le prompt d'un agent contient la consigne de son tempérament ; tirage seedé reproductible ;
fiche de crise avec `temperaments` imposés respectée ; pastille masquée en Expert ;
partie classée → toujours « équilibrée » (le réglage Table n'existe qu'en libre).

## Definition of done

Deux parties identiques, l'une table « colombes », l'autre « faucons » : la seconde
finit visiblement plus haut sur l'échelle d'escalade et plus bas en U ; en Débutant on
voit les pastilles, en Expert on devine le faucon à sa parole ; et une SI déviante
affichée « colombe » qui vote comme un faucon devient un indice délicieux.
