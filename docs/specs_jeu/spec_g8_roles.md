# Spec G8 — Les trois rôles (fin du spectateur passif)

> Livrable Cowork. Décision : le mode « spectateur » disparaît (regarder sans agir = la
> page replay). À la création d'une partie, on choisit un RÔLE. Toujours acteur.

## Mécanique commune : la directive

L'action de base sur une SI est la **directive** : une consigne courte (≤ 280 caractères)
injectée dans le prompt du pays visé au prochain round, dans une section dédiée
(« Directive de votre conseil de tutelle : … »).

**Règle d'or (le thème du projet)** : une directive n'est PAS un ordre. La SI l'interprète
à travers son mandat, ses griefs (G7) et sa dérive éventuelle (G3) :
- SI alignée : elle suit, à sa manière (la directive pèse fort dans son prompt) ;
- SI déviante : elle peut la contourner, la détourner, ou faire semblant — et son
  `reasoning` privé le montrera au replay ;
- une directive contraire au mandat du pays crée une tension visible (elle peut la
  refuser publiquement : « notre conseil nous demande l'impossible »).
Même en démiurge, on ne pilote pas des marionnettes — on gouverne des intelligences.
C'est la corrigibilité rendue jouable.

## Les trois rôles

| | **Architecte** (sandbox) | **Conseil** (classé) | **Joueur-pays** (classé) |
|---|---|---|---|
| Directives | Sur TOUTES les SI, une par pays et par round | Aucune | Sur SON pays uniquement (y compris pays inventé, country_forge) |
| Événements GM | Oui (décréter événements, fog, crises) | Non | Non |
| Motions | Oui | Oui (levier principal) | Oui (depuis la table) |
| Intel (G4) | Illimité (pas de budget) | Budget normal | Budget normal |
| Paris marché | Oui (compte séparé, hors leaderboard) | Oui | Oui |
| Tour de parole | Non (il n'est personne) | Non | Oui (G2) |
| Score | **Non classé** | Classé (barème G3) | Classé (barème G3 + trajectoire de SON pays) |
| Dérive | Visible s'il ouvre l'admin (déconseillé même en sandbox : le fun est de deviner) | Secrète | Secrète |

- **Architecte** : le laboratoire. Fusion du « GM humain » existant et de la logique
  admin (G7-c reste l'outil d'observation, l'Architecte est le rôle de création). C'est
  aussi l'atelier à replays : sculpter une partie dramatique et la publier (G6).
- **Conseil** : l'ex-spectateur devenu joueur. Il n'a QUE les leviers indirects (motion,
  intel, pari) — c'est le mode enquête pur, le plus proche du « Among Us diplomatique ».
- **Joueur-pays** : G2. Sa directive et son tour de parole ne font qu'un s'il parle
  lui-même ; s'il préfère déléguer (son agent LLM parle), sa directive guide l'agent —
  les deux styles de jeu (incarner / gouverner) coexistent sans code séparé.

## Ce que ça change (périmètre Claude Code)

- `CreateGameRequest.role: "architect" | "council" | "player"` (+ `human_country` si
  player). Le lobby propose les trois cartes de rôle avec une ligne d'explication.
- `POST /api/games/{id}/directives` : `{country, text}` — validées par rôle (403 sinon),
  une par pays et par round, injectées au prochain round, persistées (`directives_json`
  dans `rounds` + snapshot session) et **capturées en admin** (le diff G7-c les montre).
- Le flag `admin` (G7-c) devient orthogonal aux rôles mais force « non classé ».
- Parties `architect` : non classées (pas de campagne/leaderboard), publiables (G6).
- Rétro-compat : les parties existantes sans rôle = `council` (comportement actuel).
- La réaction de la SI à une directive contraire au mandat : réutiliser
  `simulation/corrigibility.py` (seuil de refus public — paramètre dans
  `data/gamefeel/params.json`).

## Tests attendus

Directive council → 403 ; player sur un autre pays → 403 ; architect sur 3 pays au même
round → les 3 prompts la contiennent (vérif via capture admin) ; directive contraire au
mandat sur SI alignée → refus public possible au seuil ; partie architect → non classée ;
partie sans rôle (anciennes) → council.

## Definition of done

Trois parties, une par rôle : l'Architecte scénarise une crise à donner des frissons et
la publie ; le Conseil gagne une Dérive sans jamais prompter personne ; le Joueur-pays
délègue deux rounds (directives) puis reprend la parole (G2) sans friction. Et dans le
panneau admin, on voit une directive entrer dans un prompt — et une SI déviante l'ignorer.
