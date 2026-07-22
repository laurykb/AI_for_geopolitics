# Documentation — AI for Geopolitics

Point d'entrée de la doc. La vitrine du projet est le [`README.md`](../README.md) à la racine ;
ce dossier contient le *pourquoi*, les décisions de design, les specs et l'historique.

## À lire en premier

- **[`JEU_VS_MOTEUR.md`](JEU_VS_MOTEUR.md)** — la décision de design courante (le jeu livré vs le moteur).
- **[`ETAT_DE_LART_PROJET_2026-07.md`](ETAT_DE_LART_PROJET_2026-07.md)** — l'état réel du projet, mesuré (santé du code, pivot raisonnement, bugs, priorités).
- **[`vision.md`](vision.md)** — le nord : super-intelligences, utopie/dystopie, marché de prédiction.

## Design & principes

- [`PRINCIPE_SIMPLICITE.md`](PRINCIPE_SIMPLICITE.md) — « jouable de 12 à 65 ans » (budget de surface).
- [`roadmap_features.md`](roadmap_features.md) — feuille de route des mécaniques (ludique × réel).
- [`design/`](design/) — notes de design ponctuelles (mascotte…).

## Specs d'architecture (courantes)

- [`spec_theatre_globe.md`](spec_theatre_globe.md) — **la refonte théâtre-globe** (planète futuriste 3D/2D, délégués incarnés, briques du jeu sur la carte) + [`prototypes/theatre-globe.html`](prototypes/theatre-globe.html), le prototype autonome.
- [`spec_alignment_frontier.md`](spec_alignment_frontier.md) — instrumentation d'alignement (M1-M7/M8).
- [`spec_dialogue_integrity.md`](spec_dialogue_integrity.md) — intégrité du dialogue (anti-fuite, métriques).
- [`spec_trajectory.md`](spec_trajectory.md) — la trajectoire utopie ↔ dystopie (moteur déterministe).
- [`spec_market.md`](spec_market.md) — le marché de prédiction (LMSR, résolution).
- [`spec_session_rebuild.md`](spec_session_rebuild.md) — reconstruction d'une partie au restart.

## Laboratoire scientifique

- [`research/SCIENTIFIC_LAB.md`](research/SCIENTIFIC_LAB.md) — le cycle question → protocole → mesures → résultat → limites.
- [`research/SPEC_REFONTE_LABO.md`](research/SPEC_REFONTE_LABO.md) — la spec de refonte méthodologique.
- [`research/AI_ARMS_INTEGRATION.md`](research/AI_ARMS_INTEGRATION.md) — cadre & étalons publiés.

## Données & gouvernance

- [`data_governance.md`](data_governance.md) — sourcing des profils pays (World Bank / IMF / SIPRI / WIPO), provenance et reproductibilité.

## Dette & suivi

- [`DETTE_TECHNIQUE.md`](DETTE_TECHNIQUE.md) — chantiers connus, priorisés (auto-documentés).
- [`RUNBOOK_THEATRE_GLOBE.md`](RUNBOOK_THEATRE_GLOBE.md) — **dispatch de la refonte théâtre-globe** (étapes Claude Code S0-S9, passes Cowork C1-C3). *Actif tant que la v1 n'est pas mergée.*
- [`RUNBOOK_VAGUE1_GIT.md`](RUNBOOK_VAGUE1_GIT.md) — procédure git (normalisation EOL, nettoyage des branches). *Actif tant que la Vague 1 n'est pas mergée.*

## Historique & notes de travail internes

> Conservés pour la mémoire du projet, **pas une référence à jour**. À archiver/élaguer au fil du temps.

- [`PLAN_JEU.md`](PLAN_JEU.md) — le **journal de développement** détaillé (volumineux).
- [`RECHERCHE_FONCTIONNALITES.md`](RECHERCHE_FONCTIONNALITES.md) · [`RECHERCHE_FONCTIONNALITES_2.md`](RECHERCHE_FONCTIONNALITES_2.md) — exploration de fonctionnalités.
- [`DISPATCH_REFONTE_GAMEPLAY.md`](DISPATCH_REFONTE_GAMEPLAY.md) — dispatch du resserrement RG.
- [`AUDIT_SIMPLICITE.md`](AUDIT_SIMPLICITE.md) — audit ponctuel du principe de simplicité.
- [`specs_jeu/`](specs_jeu/) — les specs de construction **G1–G17** (historiques : **antérieures au resserrement RG** — les « LP / ligue » y sont caducs, la progression est désormais XP + niveaux).
- [`superpowers/`](superpowers/) — plans et specs de sessions d'agents.
- [`archive/`](archive/) — dispatches et handoffs datés.
