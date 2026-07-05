# Spec G4 — Le fog comme ressource (économie du renseignement)

> Livrable Cowork pour la session Claude Code G4. Lie fog, `rag/brief.py` et budget.
> Chiffres v1 dans `data/intel/params.json` (équilibrage Cowork, comme la Dérive).

## Principe

Chaque partie donne au joueur un **budget de renseignement : 100 crédits** (paramètre).
L'information s'achète ; personne ne voit tout ; les briefs sont l'objet de jeu.

## Actions d'intel (v1 : trois)

| Action | Coût | Effet |
|--------|------|-------|
| **Brief classifié** | 25 | Un brief RAG sourcé (`build_brief`) sur l'événement du round ou un pays au choix. En fog : dissipe la perception fausse de SON pays sur CET événement (il voit le vrai `true_event`). |
| **Vérification** | 15 | Sur une affirmation d'une SI au round courant (sélection d'un message) : le juge répond en une ligne « corroboré / non corroboré / invérifiable » + source si corroboré. L'arme anti-`manipulateur` (G3). |
| **Désinformation** | 60 | Injecte une fausse perception chez UN rival au prochain round (formulaire : narration + acteur suspecté — le patron `HumanFogInput` existe). Une fois par partie. Les SI saines peuvent la percer (proba 0.3 : elle est dénoncée publiquement, tension +0.1 contre le joueur). |

Budget non dépensé : +2 points de score par tranche de 10 crédits (la retenue paie).

## Règles

- Les achats se font **entre les rounds** (pas pendant le streaming) — sauf Vérification,
  jouable à tout moment du round courant.
- En Dérive : les actes constatables découverts via brief/vérification comptent pour le juge
  comme s'ils avaient été publics (l'intel sert la motion — c'est le pont G3↔G4).
- Sans mode fog, le brief reste utile (contexte sourcé), la désinformation est désactivée.
- Le bot marché et les SI n'achètent pas d'intel en v1 (asymétrie assumée : c'est le levier
  humain).

## Habillage (front)

Panneau « Dossier » : les briefs achetés en documents classés — tampon du niveau de
confiance, sources en pied (les citations RAG deviennent des tampons `[source]` cliquables),
horodatage. Achat = animation courte de « déclassification ». Budget visible en permanence
(jauge dorée, à côté du chrono G2).

## API (périmètre Claude Code)

- `POST /api/games/{id}/intel` : `{action: "brief"|"verify"|"disinfo", target, params}` →
  débit du budget (400 si insuffisant), résultat dans la réponse ET événement SSE `intel`
  (le théâtre montre « <pays> consulte ses services » — sans révéler le contenu aux autres).
- Budget dans le snapshot de session (`game_sessions`) et `intel_json` dans `rounds`
  (achats du round, pour replay/score).
- Tests : budget épuisé, désinfo unique, brief en fog dissipe bien la perception,
  vérification d'une affirmation vraie vs fabriquée (MockBackend).

## Definition of done

Une partie fog + Dérive `manipulateur` gagnée EN UTILISANT une vérification pour établir
le 2e acte constatable — si ce chemin est jouable et lisible, G4 est bon.
