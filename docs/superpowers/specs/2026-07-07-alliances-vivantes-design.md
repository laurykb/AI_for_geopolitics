# Alliances vivantes — invention + retrait en séance (design approuvé)

Date : 2026-07-07 · Statut : **approuvé par l'user (approche A)** · Branche : `feat/roster-21-pays`
Prérequis : registre sourcé + poids moteur (spécs du même jour).

## But

Les alliances ne sont pas figées : un pays inventé peut en rejoindre à sa création, et
tout pays (humain **ou** SI) peut annoncer son retrait en pleine séance — l'effet est
immédiat, déterministe et visible (pastilles, tension, annonce du GM).

## 1. Invention : rejoindre des alliances à la création

- `InventCountryInput.alliances: list[str]` (0 à 3 tags du registre, optionnel).
- Validation : tag inconnu du registre → 400 ; la liste choisie REMPLACE celle de la
  forge. Champ omis → sortie de forge inchangée.
- Lobby : dans le bloc « Inventer mon propre pays », cases à cocher des accords du
  registre (libellé court), plafond 3, chargées via `GET /api/sources` à l'ouverture.

## 2. Retrait en séance — acte `ALLIANCE:` (patron MOTION:)

- **Parser déterministe** (`simulation/alliances.py::parse_departure`) : dans un message
  public, une ligne `ALLIANCE: quitter <X>` (tolérant : `je quitte`, `rompre`,
  `retrait de` ; X = tag exact OU nom court — « OTAN » pour NATO). Seule une alliance
  **détenue** par l'orateur compte ; pactes de partie (`pact:a+b`) brisables pareil ;
  premier acte valide du message retenu.
- **Application** (`apply_departure`) : tag retiré de `country.alliances` ;
  **+0,10 de tension** symétrique avec chaque ex-partenaire présent ; renvoie les
  ex-partenaires. Idempotent si le tag a déjà disparu.
- **Câblage round** (`game_api._handle_step`, sur `MessageDoneStep` — couvre humain et
  SI) : effet immédiat (les orateurs suivants voient le nouveau monde), entrée GM au
  transcript (« X annonce son retrait de Y »), archive `judge_json["alliances"]`,
  trame SSE `alliance_change {country, tag, name, partners}`.
- **Capacité annoncée aux SI** : note privée (comme `MOTION_CAPABILITY_NOTE`) ajoutée
  seulement si le pays détient ≥ 1 alliance.
- **Pas d'adhésion en cours de partie (v1)** : rejoindre l'OTAN en un round serait une
  fiction de trop ; les pactes bilatéraux (diplomatie existante) couvrent le besoin.

## 3. UI

- **Composeur joueur-pays** : menu « Quitter une alliance » (liste SES alliances
  actuelles) qui insère la ligne `ALLIANCE: quitter <tag>` dans le message.
- **Live** : reducer `useRoundStream` gagne le cas `alliance_change` (patron
  `motion_filed`) → bannière sobre sur la scène ; les pastilles se mettent à jour au
  resync de fin de round (elles lisent le monde serveur).

## Tests (TDD)

- Python : parser (tag, nom court, variantes verbales, non-détenue → None, inconnu →
  None, pact) ; application (retrait + tension + partenaires + idempotence) ; round API
  scripté (`AllianceAwareBackend`) : monde mis à jour, archive, trame SSE ; invention
  (tags validés, remplacement forge, 400 sur inconnu).
- JS : reducer `alliance_change` (vitest).

## Hors périmètre

Adhésion arbitrée en cours de partie (vote/juge) ; effets trajectoire ; réadhésion.
