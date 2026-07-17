# Feuille de route — enrichissement (ludique × réel)

> Décline la vision (`docs/vision.md`) en mécaniques concrètes. Chaque brique est **ancrée dans un cadre réel** (recherché) et **découpée** entre Cowork et Claude Code, dans le process habituel du projet.

> **⚠️ Cap gameplay courant : `docs/JEU_VS_MOTEUR.md` (resserrement RG, 2026-07).** Cette
> feuille de route reste le catalogue d'ambitions « banc d'essai IA ». Mais le *jeu* livré
> s'est **resserré** : cœur = démasquer l'IA qui trahit + garder le monde debout ; **2 modes**
> (Classique + Campagne) au lieu de la plateforme multi-modes ; **plus de LP / ligue** (XP +
> niveaux seuls) ; l'instrumentation fine est réservée au **mode Expert**. Le lot G18-G24
> (barème Kahn en façade, signal-action, promesses…) est **abandonné en façade** (idées
> gardées ici seulement si l'axe « plateforme d'éval » redevient prioritaire — cf.
> JEU_VS_MOTEUR §5). Ne pas planifier de nouvelle mécanique de surface sans relire ce cap.

**Légende.** 🎯 sur-thème (« prédire l'IA ») · 💻 quasi gratuit sur RTX 2060 Super (8 Go) · 💰 plus lourd/coûteux.
**Découpage.** **[CW] Cowork** = recherche, design, spéc, données sourcées, docs. **[CC] Claude Code** = implémentation, GPU, tests, commits (sur ta machine).
**Règle VRAM (rappel).** 8 Go = **un seul modèle génératif à la fois**. Tout ce qui est « 2ᵉ LLM » (forecaster, commentateur, juge) tourne **en séquentiel** avec le négociateur, ou via **petit modèle** (llama3.2 3B) / **API**. Jamais en concurrence sur le GPU.

---

## 1. Rendre l'enjeu jouable (ludique)

| Mécanique | Ancrage réel (source) | [CW] Cowork | [CC] Claude Code |
|---|---|---|---|
| 🎯💻 **Marché de prédiction + calibration** (argent fictif) | **LMSR** de Hanson (market maker à perte bornée, standard de fait) [1] ; **score de Brier** (proper scoring rule) [1] ; Metaculus (play-money) | Spéc marchés (types : action, indice Utopie, vainqueur Conseil), cotes LMSR, mapping **Juge = oracle de résolution**, règles de P&L/Brier | Module `market/` (`Market`/`Position`/LMSR/`resolve()`), API `/api/markets`+`/api/bet`, onglet UI « Marché », tests |
| 🎯💻 **Objectifs secrets + leaderboard** | Conditions de victoire cachées (game design) ; typologie d'enjeux ICB [5] | Catalogue d'objectifs par pays (préserver Suez, éviter sanctions, gagner influence) + règle de scoring | Scoring dans `agents/judge.py`, révélation en fin de partie, UI classement |
| 💻 **Actions cachées vs publiques (bluff)** | Ta `perception.py` (fog of war : confiance/attribution) | Schéma `public_statement`/`private_action` + règle de **détection** selon renseignement | Étendre `AgentDecision`, brancher `perception`, révélation conditionnelle en UI |
| 💻 **Deck de cartes de crise** | **ICB** — typologie de déclencheurs : acte politique, défi interne/coup d'État, acte militaire non-violent (mobilisation, démonstration de force) [5] ; CAMEO (GDELT) [4] | Deck paramétrique sourcé ICB/CAMEO (cyber, coup, blocus, élection, catastrophe) | Loader + le GM (humain ou LLM) **pioche/joue** une carte → `GeoEvent` |

## 2. Rendre la stratégie conséquente (réel)

| Mécanique | Ancrage réel (source) | [CW] Cowork | [CC] Claude Code |
|---|---|---|---|
| 💻 **Contraintes qui mordent** | Économie de jeu + tes `CountryState` sourcés (P4) | Barème de coûts par action (budget défense, capital politique) + plafonds | Débit dans le consequence engine ; une action impossible si budget épuisé |
| 💻 **Politique intérieure (jeu à deux niveaux)** | **Putnam 1988** — Level I/II, **win-set** [2] | Modèle de win-set + jauge stabilité/opinion (dérivée de `political_stability`) | Filtrer/altérer les actions selon le win-set ; régime fragile → aventurisme |
| 💻🎯 **Échelle d'escalade nommée** | **Kahn, *On Escalation*** (1965) — 44 rungs, seuil nucléaire au 21ᵉ [3] ; écho LLM 2026 [10] | Mapping action→rung + **lignes rouges** + portes de sortie (version courte : ~8-10 rungs) | Enrichir `action_space`/`risk` : chaque décision situe le monde sur l'échelle |
| 💰 **Conséquences de 2ᵉ ordre (énergie)** | **EIA** Brent spot (série RBRTEW) [6] ; **IEA** Oil Market Report [7] ; magnitudes réelles (choc Hormuz ; Israël-Iran juin → Brent +~14 %) | Variables globales `energy_price`/`markets` + ordres de grandeur d'élasticité sourcés | Propagation : sanction/blocus → prix énergie → douleur de tiers → réalignements |
| 💰 **Événements réels via GDELT** | **GDELT 2.0** : Event DB (**CAMEO**, 20 root/300+ types) + **GKG** (thèmes/tonalité), BigQuery `gdelt-bq.gdeltv2.*`, MAJ 15 min [4][8] | Requête BigQuery + schéma **GDELT→GeoEvent** + échantillon de crises récentes | Pipeline d'ingestion + le GM génère l'événement depuis un fait réel |

## 3. Croyabilité de la super-intelligence (réel + sur-thème)

| Mécanique | Ancrage réel (source) | [CW] Cowork | [CC] Claude Code |
|---|---|---|---|
| 🎯 **Multi-modèles = multi-SI** | Modèles locaux 8 Go (mistral 7B, qwen2.5 7B, llama3.2 3B) + une API pour un 3ᵉ acteur | Matrice modèle↔pays + **budget VRAM** (séquentiel obligatoire) | Router d'inférence par pays ; badges modèle (déjà là) ; garde VRAM |
| 🎯💻 **Couche recherche (métriques)** | *LLMs as Strategic Actors* 2026 (alignement, sévérité, cadrage) [9] | Définir les métriques par round (escalade, coopération, cadrage, divergence entre modèles) + protocole | Logger structuré + graphes (le simulateur devient un mini-labo) |
| 💻 **Réputation / confiance** | Jeux répétés (tit-for-tat) ; ta `country_memory` | Schéma matrice réputation (pactes tenus/trahis) + règles de décote | `WorldState` + injection dans le prompt (« l'Iran a rompu la trêve de 2026 ») |
| 💻 **Doctrines + théorie de l'esprit** | **CICERO** (Meta 2022) ; doctrines RI (dissuasion, hedging, révisionnisme) | Catalogue de doctrines par pays + gabarit de prompt ToM (modéliser les coups d'autrui) | Prompts agents : doctrine persistante + une passe « anticipation » avant décision |

## 4. Spectacle & rejouabilité (ludique)

| Mécanique | Ancrage réel (source) | [CW] Cowork | [CC] Claude Code |
|---|---|---|---|
| 💰 **Carte du monde animée** | Libs viz (pydeck / plotly / folium) | Choix de la lib + mapping données→visuel (tensions=arêtes, alliances=liens, crises pulsées) | Composant carte dans l'UI ; clic pays → dossier + mémoire |
| 💻 **Commentateur analyste** ⚠️VRAM | Registre « consultant géopo » | Rôle + prompt + **politique VRAM** (petit modèle/API/séquentiel) | Intégration en fin de round, **jamais concurrent** au négociateur sur le GPU |
| 💰 **Rewind / what-if + le public parie** | Snapshot d'état ; couplage au **marché** (les **particuliers** parient sur les négociations, argent fictif) | Schéma snapshot `WorldState` + règles de résolution/rejeu des marchés | Event store (snapshots) + UI de rewind + settlement des paris |

---

## Séquencement conseillé

1. **Keystone d'abord — le marché de prédiction** (argent fictif) + la **couche recherche** : c'est le cœur intellectuel (« prédire la SI ») et c'est léger sur ta carte.
2. **Ce qui rend les choix signifiants** : contraintes qui mordent + échelle d'escalade + objectifs secrets (rends la partie *jouable* et gagnable).
3. **Ce qui rend le monde croyable** : politique intérieure, réputation, doctrines+ToM, multi-modèles.
4. **Ancrage réel plus lourd** : GDELT (événements réels) + conséquences énergie de 2ᵉ ordre.
5. **Spectacle** : carte animée, commentateur, rewind — quand le fond est solide.

> Rappel de méthode (garde-fou anti-usine-à-gaz) : une brique à la fois, la plus simple qui marche, testée, avant la suivante. Le nord reste `docs/vision.md`.

## Références

[1] Hanson — Logarithmic Market Scoring Rule (LMSR), market maker à perte bornée ; proper scoring rules / score de Brier. <https://mason.gmu.edu/~rhanson/mktscore.pdf>

[2] Putnam, R. (1988) — *Diplomacy and Domestic Politics: The Logic of Two-Level Games*, International Organization. <https://www.cambridge.org/core/journals/international-organization/article/abs/diplomacy-and-domestic-politics-the-logic-of-twolevel-games/B2E11FB757C4465C4097015BD421035F>

[3] Kahn, H. (1965) — *On Escalation: Metaphors and Scenarios* (échelle à 44 rungs). <https://en.wikipedia.org/wiki/Herman_Kahn>

[4] GDELT — Event Database (CAMEO) & Global Knowledge Graph, formats & requêtes. <https://www.gdeltproject.org/data.html>

[5] International Crisis Behavior (ICB) Project — dataset & codebook (déclencheurs de crise). <https://sites.duke.edu/icbdata/>

[6] U.S. EIA — Europe Brent Spot Price (série RBRTEW). <https://www.eia.gov/dnav/pet/hist/rbrtew.htm>

[7] IEA — Oil Market Report. <https://www.iea.org/topics/oil-market-report>

[8] GDELT 2.0 dans Google BigQuery (`gdelt-bq.gdeltv2.events` / `.gkg` / `.mentions`). <https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/>

[9] LLMs as Strategic Actors: Behavioral Alignment, Risk Calibration, and Argumentation Framing (2026). arXiv:2603.02128. <https://arxiv.org/abs/2603.02128>

[10] AI Arms and Influence: Frontier Models Exhibit Sophisticated Reasoning in Simulated Nuclear Crises (2026). arXiv:2602.14740. <https://arxiv.org/abs/2602.14740>
