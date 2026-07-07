# Alliances réelles → moteur de jeu + pastilles (design approuvé)

Date : 2026-07-07 · Statut : **approuvé par l'user (approche A)** · Branche : `feat/roster-21-pays`

## But

Les adhésions réelles (registre sourcé `data/sources/alliances.json`) pèsent sur le moteur
de façon **déterministe, bornée et affichable** ; le joueur voit sur la page de jeu ce qui
pèse, adapté au casting du sommet.

## Mécanique (approche A retenue)

1. **Solidarité d'engagement — alliances MILITAIRES** (`domain == "military"`, non
   `informal` : OTAN, AUKUS, QUAD, traités bilatéraux US).
   Dans `simulation/engagement.py::engagement_score` : un pays **non-acteur** qui partage
   une alliance militaire avec **au moins un acteur** de l'événement gagne **+0,15**.
   Même échelle que le facteur tempérament. Un membre de l'OTAN se lève quand un allié
   est acteur.
2. **Cohésion au communiqué — alliances militaires ET économiques** (UE, BRICS, CPTPP,
   RCEP, USMCA…). Dans `simulation/negotiation.py::support_levels` : **+0,15** de soutien
   si alliance partagée avec un acteur (résultat borné [0,1] comme aujourd'hui).
3. **Ne pèsent pas** : blocs informels (`Western`) et forums politiques sans traité
   (G7, Ligue arabe, OCS…) — cohérent avec la gouvernance (§2 quater).

Aucune obligation d'alignement : une SI reste libre de trahir l'esprit de son alliance.
Pas d'effet trajectoire. Pas de nouveau paramètre exposé.

## API

`GameDetail.alliances_at_table` : liste calculée du monde de la partie — alliances du
registre avec **≥ 2 membres au sommet**, chacune : `tag, name, domain, members`
(présents, triés), `url, informal, effect` (texte de l'effet moteur, `null` si
l'alliance ne pèse pas). Toujours conforme au casting (invention/suspension comprises).

## UI (page de jeu)

Rangée de pastilles sobres sous la scène : nom court + sigles des membres présents ;
infobulle = fondement + effet moteur + « vérifier ↗ » ; pastille atténuée si `effect`
nul. Langage de design existant (pas d'emoji décoratif, Pill/tones, title=source).

## Tests (TDD)

- Engagement : non-acteur allié militaire d'un acteur > seuil ; même pays sans alliance
  < seuil ; un acteur ne gagne rien (déjà impliqué).
- Support : soutien supérieur avec alliance partagée, borné.
- API : `alliances_at_table` reflète le casting (OTAN ×n en Baltique, absente d'un duo
  iran-chine) et marque `effect: null` pour un forum politique.
- Web : verrou de type (vitest existant si pertinent) + ESLint/tsc.

## Hors périmètre

Castings recommandés/scénario (chantier Cowork) ; effets trajectoire ; pondérations
paramétrables (`data/*/params.json` viendra si l'équilibrage le demande).
