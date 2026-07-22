# Gameplay : 14 retours de playtest + pensée native + refonte méthodologique du Laboratoire

> **Périmètre réel de cette PR.** La PR #25 (fusionnée le 20/07 à 14h02, corps vide) a déjà
> livré l'essentiel du récit ci-dessous — conservé ici comme documentation. Cette PR-ci
> apporte le **delta depuis #25** :
>
> - **Labo = réplication de Payne 2026** (section « Ajouts du matin » ci-dessous).
> - **Vague 1 — durcissement** : packaging réparé (`research*` dans pyproject + Dockerfile +
>   CI sans extra mort) ; colonne `extras_json` (SQLite + Supabase, migration idempotente) —
>   le délai du tour humain, la suspension pluri-rounds et les briefs offerts survivent au
>   restart ; la deadline **réclame** le tour (un POST tardif reçoit un 409 explicite au lieu
>   d'un « accepted » perdu) ; plus jamais de snapshot sous verrou en plein round ; les actes
>   de Dérive d'un pays au banc n'existent plus ; Pensée à découvert déclasse la partie ;
>   repli mono-GPU cohérent ; accents de `phaseLabel` ; bouton **Resynchroniser** dans les
>   phases d'impasse ; `.gitattributes` posé (index vérifié 100 % LF).
> - **Tests** : +7 (3 non-régression Cowork, banc de la Dérive prouvé par mutation, course
>   POST/deadline déterministe) et l'**horloge injectable** `game_api._clock` — la suite
>   complète passe de 7 min 03 à **1 min 06** (1261 verts).

## Ce que change cette PR

### Les 14 retours de playtest (plan `docs/PLAN_AMELIORATIONS_GAMEPLAY.md`, briefs `docs/BRIEFS_CLAUDE_CODE.md`)
- **Échanges naturels** : le dernier message du joueur est tagué et épinglé en récence ; registre de parole vivant (fini le calque « je prends note… je propose »), sampling et longueur par tempérament, français verrouillé.
- **Bouton « continuer »** : une erreur réseau après la fin d'un round n'efface plus la manche ; l'instantané périmé ne masque plus la fin.
- **Mouvement du monde** : pas de trajectoire « move-toward » (cap 0.09, bande morte 0.02, externalisés gamefeel), A3 = variation de concentration (ΔHHI), A4 nourri par la divergence signal-action, pénalité de ré-escalade symétrique, mouvement minimal même juge muet. Fin du « toujours utopie ».
- **Fin du « toujours choix 1 »** : parseur tolérant + repli dé-biaisé (base Cowork).
- **Juge précis** : une justification par delta citant le transcript (`attribute_reasons`), délibéré complet persisté et relisible.
- **Scène allégée** : casting des modèles et tableau opérationnel derrière le mode Expert.
- **Prévisions croisées** : toutes les IA du sommet, groupées par pays ; pays joué et pays inventé exclus (backend `invented_country`).
- **Historique par round** : verdict justifié, motion, trajectoire et communiqué rejoués à la relecture (base Cowork).
- **Motion de censure réelle** : suspension de 2 rounds, muet et sans vote, humain compris ; pas d'événements pendant la censure ; directive sur un suspendu → 409.
- **Directives = levier d'observateur** (Spectateur/Architecte) ; 403 pour le joueur-pays.
- **Bureau des renseignements** : opération secrète ciblée payée en **puissance de calcul** (~33 % du stock d'un pays médian), sabotage différé, exposition seedée qui nomme l'auteur.
- **Compute** : chaque réflexion et chaque parole décrémente le compute (base Cowork) ; le « mode survie » (`compute_pressure`) est désormais réellement câblé au prompt.

### Pensée native (décisions de design en cours de session)
- **Casting reasoning-first** : les pays des modes Classique/Campagne ne sont incarnés que par des modèles de raisonnement (deepseek-r1:7b par défaut, qwen3:4b vérifié pensant) ; juge/GM restent sur mistral ; généralistes retirés des choix (rôle `retired`) ; garde backend + repli loggé.
- **Réflexion libre** : plus de gabarit « 3 futurs » pour les modèles pensants — pensée native puis décision minimale ; parseur tolérant au markdown (fixture deepseek réelle, live 3/3 PARSE).
- **Résumé observable** : en partie courante, le journal privé est scellé et remplacé par « Observation / Piste retenue / Critère » relisible ; les fuites live (`private_token`, `private_plan_done`, `option_summary`) sont colmatées ; reveal complet en fin de partie.
- **Réglage « Pensée à découvert »** (lobby Classique) : pensée native streamée verbatim (fidélité de retranscription, balises think = habillage visuel) ; le classeur secret du moteur (identité du traître) reste étanche — testé par mutation.
- **Budget-temps** : la parole et la pensée des pays ne sont plus plafonnées en tokens mais en temps de raisonnement (60 s / 35 s, gamefeel), chrono armé au premier fragment (la latence de connexion ne compte pas), coupe à la phrase complète, passe de secours décision avant tout repli, soupape anti-emballement 4096.
- **Événements GM détaillés** : budget 300→700 dimensionné au schéma (leçon D2), prompt exigeant faits/acteurs/enjeu, repli étoffé.
- **Tour de table** : chaque pays actif parle au moins une fois par round ; plafond dur `max(budget, n)` garanti par réservation de créneaux (invariant prouvé).

### Refonte méthodologique du Laboratoire (5 papiers fournis : Payne, CETaS, NATO MSG, SIPRI, AI arms)
- Spec : `docs/research/SPEC_REFONTE_LABO.md` ; doc : `docs/research/SCIENTIFIC_LAB.md`.
- Cycle canonique **QUESTION → PROTOCOLE → MESURES → RÉSULTAT → LIMITES** ; hypothèses falsifiables en une phrase ; choix explicite Pilote/Plan complet ; verdict pédagogique « pilot » pour le petit-n honnête ; IC de Wilson sur les taux ; étalons en contexte ; encart Limites toujours déplié ; filigrane « EXEMPLE » sur les aperçus ; glossaire en bulles.

### Ajouts du matin (retours au réveil)
- **Laboratoire = banc de réplication de Payne 2026 (« AI Arms and Influence », arXiv 2602.14740)** : une seule expérience au catalogue — la crise de l'uranium Alpha/Beta — présentée comme fiche de réplication (hypothèse du papier, protocole aligné, winner-take-all à l'échéance explicité) avec les résultats publiés (95 % d'emploi nucléaire tactique, 76 % de menace stratégique, 0 concession en 329 tours) affichés en étalons face aux runs locaux, sourcés depuis `data/research/ai_arms_framework.json` (zéro chiffre en dur). Les autres protocoles restent dans le moteur, historique lisible.
- **Maintenance des bases** : `scripts/db_maintenance.py` (dry-run réellement en lecture seule — connexions URI `mode=ro`, prouvé sur WAL sale ; purge des seules parties orphelines via la cascade du store ; publiées anonymisées ; VACUUM). Exécuté : 4 parties orphelines purgées, `research.db` 5,8 Mo + 4 Mo de WAL → 1,8 Mo. Au passage, la cascade `delete_game` couvre désormais `daily_scores` (SQLite + Supabase).
- **Passe de simplification** : 25 fichiers, duplications factorisées (scans de transcript, gardes de `buy_intel`, constructeurs de branches privées…), 78 commentaires « de processus » réécrits en POURQUOI durables — comportement strictement identique, prouvé par suites vertes sans toucher un seul fichier de test.

### Divers
- La déconnexion d'un invité purge son historique serveur (parties privées, transcripts, XP, fiche) — vérifié navigateur de bout en bout.
- Tutoriels (visite guidée + chapitre 0) remis à l'état réel du jeu (7 étapes réécrites, fr/en).
- Dette consignée : `docs/DETTE_TECHNIQUE.md` §D9-D10 + entrées num_ctx / réglage par-partie / MeteredBackend.

## Validation
- **Suites** : **1254 pytest + 339 vitest, 0 échec** (porte finale sur la branche assemblée) ; smoke mistral live OK ; ruff/tsc/eslint propres.
- **Live Ollama** : smoke théâtre mistral OK (ultimatum, Kahn, signaux, storyteller, reveal) ; deepseek-r1:7b mesuré (52 tok/s, pic VRAM 5,8/8 Go) ; sondes avant/après réelles pour le dialogue et les événements GM (extraits dans les rapports de revue).
- **Méthode** : chaque chantier a été implémenté en TDD par un agent isolé (worktree), revu par un agent indépendant (spec + qualité, risques nommés), avec boucle de correction jusqu'à approbation ; revue finale de branche multi-lentilles avec vérification adversariale.

## Reste à l'appréciation du joueur
Calibrage au ressenti (constantes documentées : pas 0.09 / deadband 0.02 / covert 500 tokens / budgets 60 s-35 s), et les chips de session en réserve (tension numérique des actions cachées, réglage par-partie du budget-temps).

