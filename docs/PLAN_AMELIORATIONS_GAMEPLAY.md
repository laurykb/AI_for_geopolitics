# Plan d'améliorations gameplay — AI for Geopolitics

> Établi après diagnostic du code réel (backend `simulation/` · `agents/` · `app/game_api.py`, front `web/src`).
> Chaque cause racine est citée avec fichier + ligne. Objectif : traiter tes 14 retours de jeu en répartissant
> proprement le travail entre **Cowork** (correctifs isolés et déterministes, testables sans Ollama) et
> **Claude Code en local** (ce qui exige Ollama, l'app en marche, ou du réglage au ressenti).

---

## 1. Principe de répartition

| Critère | → Cowork (ici, via le pont fichiers) | → Claude Code (local) |
|---|---|---|
| Nature | Bug isolé, logique pure, diff contenu | Comportement LLM, ressenti, réglage |
| Vérifiable par | `pytest` / `vitest` déterministe | Partie live + Ollama + œil humain |
| Fichiers concernés | Présents dans le snapshot | Touchent `inference/`, `core/`, `kahn.py`, `gamefeel.py`, `data/*.json` (hors snapshot) |

Trois fichiers-clés du réglage (`simulation/kahn.py`, `simulation/gamefeel.py`, `data/*/params.json`) **ne sont pas** dans ce que j'ai rapatrié : tout ce qui les touche revient naturellement à Claude Code, qui a l'arbre complet.

---

## 2. Matrice des 14 points

| # | Retour de jeu | Cause racine (fichier:ligne) | Effort | Test | Propriétaire |
|---|---|---|---|---|---|
| 4 | IA choisissent **toujours le choix 1** | `fallback_private_plan` code `selected_branch=1` en dur (`private_deliberation.py:362`) + parseur trop strict (`_parse_observable_journal:217-271`) qui déclenche ce repli | M | Déterministe | **Cowork** (+ valid. live) |
| 1 | Échanges peu naturels, IA ignorent le joueur | Déclaration publique issue de `public_brief()` générique (`llm_agent.py:258`), message joueur noyé dans fenêtre de 14 (`negotiation.py:274`), placé avant la tâche au lieu de la position de récence (`prompts.py:331`) | M | Mixte | **Claude Code** (ressenti) |
| 5 | Raisonnement « moderne » (reasoning LLM) | Aucun support de modèle de raisonnement ; backend appelé sans option *think*, aucun strip `<think>` ; défaut `mistral` 7B généraliste | L | Live | **Claude Code** |
| 2 | Bouton **« continuer »** bugue | Réducteur : `error` écrase l'état `done` (asymétrie avec `interrupted`, `useRoundStream.ts:419-421`) ; `deriveGamePhase` teste un `awaiting_human` périmé avant `done` (`game-phase.ts:55`) | M | Déterministe | **Cowork** |
| 14 | **Puissance de calcul** ne décrémente plus | `consume()` (`compute.py:89`) **jamais appelée** — code mort ; aucun débit branché dans `run_negotiation_round` | M | Déterministe | **Cowork** |
| 10 | Motion de censure « pas appliquée » | Le filtre marche déjà (`game_api.py:1341,1404`). Symptôme = l'accusé plaide au round de débat (`motions.py:62`) + suspension d'1 round | S | Déterministe | **Cowork** (après décision design) |
| 11 | Événements **pendant** la censure | `flash_after` armé sur `session.escalation` seul, sans garde `motion is None` (`game_api.py:1349`) | S | Déterministe | **Cowork** |
| 3 | Trop peu de mouvement, **toujours utopie** | Indice U déterministe plafonné à ±0,05/round et auto-amortissant (`trajectory.py:38,251-256`) ; équilibre > 0,55 tiré par A3=1−HHI et bonus désescalade ×1,5 asymétrique (`live_round.py:801-808`) ; attributs doublement rétrécis (`negotiation.py:289`) | M | Déterministe | **Claude Code** (réglage) |
| 8 | Juge pas assez **précis / justifié** | `attribute_deltas` = nombres nus sans justification (`prompts.py:537`) ; prose et chiffres = 2 appels déconnectés ; délibéré jamais persisté (pas de branche `JudgeTokenStep`) | M | Mixte | **Claude Code** |
| 9 | **Historique cliquable** de ce qui a bougé | Données déjà persistées (`RoundView` porte deltas/judge/trajectory) ; la relecture n'affiche qu'événement + bulles (`round-transcript.tsx:51-63`) | S | Déterministe | **Cowork** |
| 6 | Nouvelle scène **trop chargée** | 8 blocs empilés ; `ModelCastPanel` + `OperationalPicturePanel` en façade et ouverts (`page.tsx:1191-1210`) au lieu d'être derrière `showEngine` | S–M | Live | **Claude Code** |
| 7 | Voir **toutes** les prévisions croisées | Backend calcule déjà tous les pays ; `slice(-6)` global s'effondre sur un seul (`scenario-forecast-panel.tsx:61`) ; aucune exclusion joueur/pays créé | M | Mixte | **Cowork** |
| 12 | Directives **réservées au spectateur** | Règle inversée : le joueur-pays rend le composeur, le spectateur est masqué (`directive-composer.tsx:38`, `game_api.py:3839`) | S | Déterministe | **Cowork** |
| 13 | Refonte **bureau des renseignements** (actions cachées, coûte du compute) | `disinfo` est déjà le patron « action cachée différée + exposition » ; `compute.py` fournit la ressource à débiter ; manque l'action `covert` dans `buy_intel` | M | Mixte | **Claude Code** (tranche verticale + équilibrage) |

---

## 3. Détail par lot

### Lot A — Raisonnement libre des IA (points 4, 1, 5) — *le cœur*

**Point 4 (central).** Il n'existe aucun `argmax` : le choix vient du texte du modèle, mais le parseur `_parse_observable_journal` exige un format trop rigide (3 blocs FUTUR + ACTION + CHAÎNE CAUSALE + CHOIX + CRITÈRE + INCERTITUDE). À la moindre déviation d'un 7B → `None` → `fallback_private_plan()` qui **fige `selected_branch=1`** et sert le même compromis coopératif fade (ce qui explique aussi le côté « peu naturel » du point 1). Aggravé par une température privée abaissée (`llm_agent.py:192`) qui renforce le biais de primauté vers FUTUR 1.

Correctif : (a) repli **non biaisé et situationnel** (ne plus coder 1 en dur — choisir selon tension/mandat, ou repli « décision unique » minimal) ; (b) **assouplir le parseur** (rendre CRITÈRE/INCERTITUDE optionnels, tolérer en-têtes variantes) pour qu'il cesse de tomber sur le repli ; (c) consigne **anti-primauté** dans le prompt + remonter la température privée ; (d) exposer le **taux de repli** comme métrique (déjà `last_private_valid`, `llm_agent.py:205`). → *Cowork peut tout écrire et tester en unitaire ; validation « ça varie vraiment » en live.*

**Point 1.** Rendre la parole du joueur **saillante** : la tagger dans `format_transcript` et l'épingler hors fenêtre (toujours inclure le dernier message humain) ; remettre le dialogue en **position de récence** (après la tâche, conforme à la docstring) ; enrichir `public_brief()` d'un « point auquel je réponds ». → *Le ressenti se juge en live → Claude Code, mais Cowork peut préparer les changements de `format_transcript`/prompt.*

**Point 5.** Ajouter un `role="reasoning"` au registre + un modèle de raisonnement 7-8B Q4 au panel ; passer l'option *think* d'Ollama selon le rôle ; **strip `<think>…</think>`** avant parse et avant l'envoi à la scène (la trace ne va qu'à l'audit privé). ⚠️ Dépend du point 4 : sans parseur tolérant + strip, une trace de pensée casse tout et renvoie au choix 1. Touche `inference/backend.py` (hors snapshot). → *Claude Code.*

### Lot B — Round, compute, censure (points 2, 14, 11, 10)

**Point 2 (bouton continuer).** Deux correctifs déterministes : garder `error` contre `done` (symétrie avec `interrupted`) dans le réducteur ; tester `liveStatus === "done"` **avant** l'instantané `awaiting_human` périmé dans `deriveGamePhase`. Plus une vérif du *flush* de dernière trame SSE dans `sse.ts` (non rapatrié). Réducteur et `deriveGamePhase` sont déjà exportés → tests vitest directs. → *Cowork.*

**Point 14 (compute).** Brancher `consume()` dans `run_negotiation_round` : débiter à chaque **réflexion** et chaque **parole** IA (coût forfaitaire `compute_cost(max_tokens)` ou tokens réellement streamés). Persistance automatique (snapshot par round). Décisions mineures : le tour humain coûte-t-il ? les votes de motion ? → *Cowork, test pytest « compute strictement décroissant, clampé à 0 ».*

**Point 11 (événements pendant censure).** 1 ligne : `if session.escalation and motion is None:` avant d'armer `flash_after` (`game_api.py:1349`). Tous les autres canaux (event du round, motions IA, fog) ont déjà la garde `motion is None` ; le flash est l'oubli. → *Cowork.*

**Point 10 (censure).** ⚠️ **Décision de design requise** (voir §4) : le filtre fonctionne déjà. À trancher : durée de suspension (1 → 2-3 rounds ?), l'accusé plaide-t-il encore, et lisibilité UI. Une fois tranché, le correctif est S. → *Cowork.*

### Lot C — Juge, attributs, historique (points 3, 8, 9)

**Point 3 (mouvement / utopie).** L'indice U n'est **pas** piloté par le juge mais par des signaux déterministes : cap ±0,05 auto-amortissant, A3=`1−HHI` (haut dès qu'il y a plusieurs pays, jamais lié à la négo), A4 qui retombe à 0,5 en mode négocié, bonus désescalade ×1,5 **asymétrique**. Correctifs : remonter/refondre le cap (pas fixe vers le signal), rebaser A3 sur la *variation* de concentration, alimenter A4 avec la diplomatie, rendre le bonus symétrique, garantir un mouvement minimal quand le juge est muet. Touche `kahn.py`/`gamefeel.py`/`data` + demande du **playtest**. → *Claude Code.*

**Point 8 (juge précis).** Enrichir le schéma `Verdict` : `attribute_deltas` passe de `float` à `{value, reason}` par attribut ; exiger une justification chiffrée citant le transcript ; **persister le délibéré** (brancher `JudgeTokenStep` → `JudgeRecord.rationale`) et l'afficher. Qualité réelle testable seulement en live. → *Claude Code (Cowork peut préparer le schéma + validators tolérants).*

**Point 9 (historique).** Le moins cher et très rentable : dans la branche `viewed` de `round-transcript.tsx`, **rendre** `VerdictPanel` (deltas), le mini-cadran trajectoire et le communiqué à partir de `viewed` (tout est déjà chargé dans `RoundView`). La timeline cliquable existe déjà (`page.tsx:807`). → *Cowork (pur front, sans Ollama).*

### Lot D — Scène, prévisions, directives, renseignement (points 6, 7, 12, 13)

**Point 6 (scène allégée).** Passer `ModelCastPanel` et `OperationalPicturePanel` derrière le flag **déjà existant** `showEngine` (`page.tsx:258`) ; garder max 3 observables légers par défaut (Alliances, Deadline, storyline). Se juge à l'œil → *Claude Code.*

**Point 7 (prévisions croisées).** Remplacer le `slice(-6)` par un **groupement par source** sur le round le plus récent, une ligne par pays du sommet, en **excluant le pays joueur et le pays créé**. `play_as` existe déjà côté front ; exposer `invented_country` dans `GameDetail` (petit ajout backend). → *Cowork (front + petit backend) ; rendu à confirmer en live.*

**Point 12 (directives).** Inverser la garde : rendre pour `spectator` (cibles = tous les pays), `null` pour `player`. Côté backend `post_directive`, retirer le 403 spectateur et rejeter le joueur. → *Cowork, test pytest des gardes.*

**Point 13 (renseignement / covert ops).** Nouvelle action `"covert"` dans `buy_intel`, calquée sur `disinfo` (ciblée, différée via `pending_covert`, exposition seedée `disinfo_exposed`), mais **payée en puissance de calcul** : `compute.consume(world.countries[human_country], gros_tokens)`. Effet 1er jet = sabotage (baisse `compute`/`stabilité` de la cible ou perception dégradée). UI : bloc à côté de la Désinformation, affichant le **coût compute**. Garde-fou éthique : sabotage/perception, jamais d'action létale. Tranche verticale + équilibrage → *Claude Code (Cowork peut poser le modèle de données + endpoint).*

---

## 4. Décisions de design à trancher

1. **Censure (point 10).** Durée de suspension : rester à 1 round, ou 2-3 ? L'accusé garde-t-il son droit de plaider au round de débat ? Faut-il un bandeau plus visible « SUSPENDU » ?
2. **Coût compute (points 13, 14).** Barème : combien coûte une parole IA, une réflexion, et une opération cachée ? (À calibrer pour que ce soit tendu sans bloquer.)
3. **Modèle de raisonnement (point 5).** Quel modèle Ollama viser sur ta RTX 2060S 8 Go (ex. un DeepSeek-R1-distill 7-8B Q4 / QwQ-like) ?
4. **Seuil « utopie » (point 3).** Recalibrer le pas *et* le seuil 0,55, ou seulement le pas ?

---

## 5. Ordre d'exécution recommandé

1. **Quick wins déterministes (Cowork)** : 11 (1 ligne) → 14 (compute) → 12 (directives) → 2 (bouton continuer) → 9 (historique) → 7 (prévisions). Gains immédiats, faible risque, testables.
2. **Point central (Cowork)** : 4 (repli non biaisé + parseur tolérant) — le plus gros effet sur le ressenti.
3. **Claude Code en local** : 1 (naturel), 5 (raisonnement moderne), 3 (réglage utopie), 8 (juge), 6 (scène), 13 (covert ops) — tout ce qui se juge en partie live avec Ollama.

---

## 6. Annexe — briefs prêts à coller pour Claude Code

*(fournis dès que tu valides le plan ; un brief par point, avec fichiers, correctif attendu et tests à écrire)*
