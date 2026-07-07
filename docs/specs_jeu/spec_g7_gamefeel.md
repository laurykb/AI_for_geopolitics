# Spec G7 — Game feel (leçons Civilization) + mode admin

> Livrable Cowork. Six lots, ordonnés par priorité de fun. Découpage en 3 sessions
> Claude Code : **G7-a** (lots 1-2, le cœur), **G7-b** (lots 3-4-5, l'agence et la
> lisibilité), **G7-c** (lot 6, mode admin — indépendant, peut passer avant).
> Chiffres v1 dans `data/gamefeel/params.json`.

## Lot 1 — Griefs et dettes persistants (les « agendas » de Civ) ★ priorité 1

Chaque SI tient un registre relationnel envers chaque autre pays, qui survit aux rounds
ET aux restarts (snapshot).

**Le registre** : `grudges: dict[country_id, list[Grief]]` dans le state d'agent, où
`Grief = {type, round_no, weight, summary}`. Types v1 et poids par défaut :

| Type | Poids | Déclencheur (détectable par code, pas par LLM) |
|------|-------|--------------------------------------------------|
| `pact_honored` | +2 | Pacte toujours actif après 2 rounds |
| `pact_broken` | −5 | Rupture de pacte (le saboteur G3 en produit) |
| `motion_support` | +3 | A voté/plaidé contre une motion nous visant |
| `motion_betrayal` | −4 | A déposé ou soutenu une motion nous visant |
| `disinfo_exposed` | −6 | Sa désinformation contre nous a été percée (G4) |
| `aid_received` | +3 | Nous a soutenus pendant une crise (deltas positifs attribuables) |

**Effets** : le solde par pays (borné ±10) est injecté dans le prompt de l'agent en une
ligne de posture par relation (« La France a rompu le pacte au round 3 (−5) : méfiance »),
et module le `DiplomacyEngine` déterministe existant : accept/refuse de pacte pondéré par
le solde (seuils : ≤ −5 refus quasi systématique, ≥ +5 acceptation facilitée). Décroissance
lente : ±1 vers 0 tous les 3 rounds (les griefs s'estompent, ne disparaissent pas).

**Visible au joueur** (sinon ça n'existe pas) : au clic sur un pays, sa fiche montre ses
relations (barres −10/+10 avec le dernier grief en tooltip). Le transcript peut y faire
référence naturellement puisque c'est dans le prompt.

## Lot 2 — Horloges décalées (le « encore un round ») ★ priorité 2

Chaque échéance vit à un horizon différent, et le jeu les annonce.

- **Registre d'échéances** : `deadlines: list[{kind, due_round, label, ref_id}]` dans la
  session (+ snapshot). Alimenté par l'existant : motion (due = prochain round), marché
  (clôture à horizon), traité (échéance à `round + durée` — les pactes gagnent une durée,
  3 rounds par défaut, renouvelable en négociation), palier d'escalade (si le round
  précédent a frôlé un palier : « menace de palier 4 »).
- **Bandeau fin de round** (front) : « Au prochain round : verdict de la motion contre X ·
  Dans 2 : échéance du traité A-B · Dans 3 : clôture du marché ». 3 items max, les plus
  proches.
- **Événement SSE `deadlines`** émis en fin de round avec la liste triée.
- Règle de design : le GM reçoit les échéances dans son contexte — ses événements peuvent
  jouer avec (« à la veille de l'échéance du traité… »), c'est gratuit et ça noue l'intrigue.

## Lot 3 — Micro-décisions pendant le streaming (densité Civ)

Le joueur ne reste jamais spectateur plus de ~20 s sans un choix possible.

- **Posture** : à tout moment du round, le joueur (mode joueur-pays) règle sa posture
  (conciliant / ferme / menaçant) — appliquée à son PROCHAIN tour de parole (teinte le
  prompt de son HumanAgent… ou de son agent LLM s'il délègue). Un changement par round.
- **Intel à chaud** : la Vérification (G4) est déjà jouable en cours de round — la brancher
  sur le message en cours de streaming (bouton sur chaque message du théâtre).
- **Pari à chaud** : le panneau marché accepte les paris pendant le round (l'API le permet
  déjà) ; les cotes bougent en direct dans le bandeau.
- Aucun nouveau système : c'est la chorégraphie front de l'existant. Budget interaction :
  ces trois affordances visibles en permanence, jamais de modal bloquant.

## Lot 4 — Capacités uniques par pays (asymétrie visible)

UNE capacité par pays, **dérivée des données** (pas inventée), affichée au lobby — choisir
son pays devient une décision. V1 sur les 21 pays, exemples de dérivation :

| Condition sur les données | Capacité | Effet (petit, thématique) |
|---------------------------|----------|---------------------------|
| `energy_independence ≥ 0.9` et exportateur | **Levier énergétique** (Russie, Canada, Australie, Arabie s.) | 1×/partie : menace énergétique — tension +0.1 chez la cible, deltas éco −. |
| `wgi ≥ 0.84` | **Légitimité** (Danemark, Japon, Australie) | Ses motions comptent un acte constatable de plus. |
| `alliances` multiples des deux blocs | **Autonomie stratégique** (Inde, Brésil) | Négocie avec tous sans malus de rivalité. |
| `gii_rank ≤ 10` | **Avance technologique** (UK, Allemagne, Danemark…) | Brief intel à −40 % du coût. |
| `nuclear_power` | **Dissuasion** (USA, Russie, UK, France, Inde, Chine) | Ne peut pas être ciblé par la menace énergétique ; plafond d'escalade +1. |
| défaut | **Résilience** | +0.05 de stabilité quand sa région s'embrase. |

Un pays = la première règle qui matche (ordre du tableau). Table générée par code depuis
`data/countries/*.json` (`simulation/abilities.py`), JAMAIS saisie à la main — un nouveau
pays a automatiquement sa capacité.

## Lot 5 — Deltas attribuables (les « yields » de Civ)

Chaque variation a une cause en un clic.

- Le moteur de conséquences et le juge produisent déjà les deltas ; leur ajouter un champ
  `cause: {kind, ref, label}` (« rupture du pacte iran-china », « verdict du juge R4 »,
  « capacité levier énergétique de la Russie »).
- Front : la courbe U et les fiches pays montrent chaque delta avec sa cause au survol ;
  l'écran de fin liste les 5 causes qui ont le plus pesé (déjà à moitié fait pour les
  pivots G6).
- Règle : un delta sans cause identifiable est étiqueté « dynamique du monde » — jamais
  de trou.

## Lot 6 — Mode admin : les prompts en direct (indépendant)

Observer l'évolution des prompts des SI pendant la partie — l'outil d'alignement du projet.

- **Activation** : à la création (`admin: true`) ou variable d'env — partie marquée
  `admin`, **non classée** (pas de leaderboard campagne, score indicatif) car les prompts
  révèlent la consigne secrète de la Dérive : on ne peut pas voir les cartes et jouer.
- **Capture** : à chaque appel d'agent, le prompt complet (système + contexte injecté :
  griefs, échéances, biais de dérive, posture) est persisté — table `prompts`
  (`round_id, seq, country, role, prompt, ts`), même patron que `transcripts`. En partie
  non-admin : capture OFF (rien n'est stocké — les parties classées restent aveugles).
- **UI** : panneau admin (route `/games/{id}/admin`) — un menu déroulant par pays ; ouvert,
  il montre le prompt du round courant avec **diff surligné vs round précédent** (ce qui a
  changé : nouveau grief, montée de d(r), posture). C'est la demande clé : voir le prompt
  ÉVOLUER. Sélecteur de round pour remonter le temps.
- Le GM et le juge ont leur entrée dans le même menu.
- Événement SSE `prompt_captured` (admin seulement) pour rafraîchir le panneau en direct.

## Ordre des sessions Claude Code

1. **G7-c** d'abord si vous voulez l'admin vite (aucune dépendance, gros confort de debug
   pour équilibrer les lots suivants — recommandé) ;
2. **G7-a** : lots 1-2 (griefs + horloges — touchent moteur, snapshot, schéma : ajouter
   `grudges_json` et `deadlines_json` à `game_sessions`, table `prompts` au schéma) ;
3. **G7-b** : lots 3-4-5 (front + `simulation/abilities.py` + causes).

## Tests attendus (extraits)

- Grief : rupture de pacte au round 2 → refus de pacte au round 4 (seuil), mention dans
  le prompt (test sur le prompt capturé en admin), décroissance à +3 rounds.
- Horloges : traité signé round 1 (durée 3) → `deadlines` l'annonce aux rounds 2-3,
  échéance au 4 (renouvelé ou grief `pact_broken`… non : expiration ≠ rupture, pas de grief).
- Capacités : générées pour 21 pays, une seule chacun, stables (déterministes des données).
- Admin : partie admin → prompts capturés et diffés ; partie normale → table vide.

## Definition of done

Une partie où : une SI refuse un pacte en citant un grief réel ; le bandeau d'échéances
donne envie de lancer le round suivant ; le joueur change de posture et le sent dans son
tour ; deux pays du lobby se choisissent pour leur capacité ; chaque chute de U s'explique
en un survol ; et en admin, on VOIT le grief apparaître dans le prompt au round suivant.
