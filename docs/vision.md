# Vision — AI for Geopolitics (le nord du projet)

> Fusion du « pourquoi » (monde de super-intelligences, utopie/dystopie) et du « comment le rendre vivant » (mécaniques ludiques + réalistes), avec le **marché de prédiction** comme clé de voûte.

> **Cap gameplay courant (2026-07, resserrement RG) : `docs/JEU_VS_MOTEUR.md`.** Cette
> vision reste le *pourquoi* et le moteur ; le *jeu*, lui, s'est resserré. Concrètement :
> le cœur jouable est **démasquer l'IA qui trahit (1 ou 2, nombre caché) tout en gardant
> le monde debout** ; **deux modes seulement** (Classique + Campagne), Brouillard et Réel
> devenus des réglages ; progression = **XP + niveaux** (les **LP / la ligue sont
> supprimés**, blasons rebranchés sur le niveau) ; l'instrumentation (M1-M7, jauges fines)
> vit en **mode Expert / onglet Informations**, pas en façade. Lire JEU_VS_MOTEUR avant
> toute reprise gameplay pour ne pas redériver vers l'ancienne plateforme.

## Le pitch en un paragraphe

Un futur proche où les États ont délégué leur diplomatie de sommet à des **super-intelligences** (plus intelligentes que les humains). Le simulateur **met en scène** ce monde à la plus haute instance étatique, **mesure** s'il penche vers l'**utopie** (coordination, abondance, désescalade) ou la **dystopie** (domination, opacité, humains hors de la boucle), et laisse un public **parier sur ce que feront ces IA** — un *Polymarket des super-intelligences*. Chaque partie est un futur possible ; la question n'est pas tranchée, elle est **explorée**.

## Trois piliers

1. **Le Monde** — des super-intelligences négocient pour des États ; une **trajectoire Utopie↔Dystopie** mesurable émerge des rounds.
2. **Le Théâtre** — *(déjà construit)* délibération live, Juge LLM, communiqué, fog of war, mémoire, rôles.
3. **Le Marché** — **prédire les super-intelligences** : miser, résolution par le Juge (oracle), gagner/perdre, classement, calibration.

---

## Pilier 1 — Le Monde (croyable et conséquent)

**Des super-intelligences, pas des diplomates.**
- **Décalage principal↔agent (le germe dystopique).** Chaque SI a un objectif propre *légèrement désaligné* de son État. Le drame naît quand une SI **déborde son mandat** — on le rend visible.
- **Portrait, pas prédiction.** Un modèle 7-8B local ne *sera* pas surhumain : on met en scène l'*idée* de superintelligence par la **structure** (mémoire parfaite, accès total au corpus RAG, outils de théorie des jeux, registre de calme et de vue longue), pas par le QI du modèle. Pendant de l'éthique « je ne prédis pas la guerre » : *je mets en scène la superintelligence pour la penser*.

**Trajectoire Utopie–Dystopie (le vrai payoff).** À côté du risk engine, 5 axes civilisationnels que le **Juge** met à jour chaque round :
1. coordination ↔ domination
2. agentivité humaine **conservée ↔ cédée**
3. pouvoir **distribué ↔ concentré** (multipolaire vs hégémon SI)
4. **transparence ↔ opacité** des intentions réelles
5. bien-être/abondance ↔ immisération

En fin de round, le monde est placé sur une **carte Utopie–Dystopie**. À la fin : « quel monde a-t-on obtenu, et pourquoi ? »

**Ce qui fait mordre le réel** (mécaniques réalistes) :
- **Contraintes qui coûtent** : sanctionner s'auto-inflige, mobiliser coûte en stabilité — branché sur les `CountryState` sourcés (P4).
- **Échelle d'escalade nommée** : diplo → éco → zone grise → militaire → nucléaire, avec **lignes rouges** et portes de sortie.
- **Réputation & mémoire** : qui a tenu/trahi les pactes est retenu et cité → alliances **émergentes**.
- **Politique intérieure** : un régime fragile se bride ou détourne par l'aventurisme (jeu à deux niveaux).
- **Multi-modèles = multi-super-intelligences** : mistral pour un pays, llama pour un autre, une API pour un 3ᵉ → on observe *réellement* des IA différentes.
- **Événements réels via GDELT** : le Game Master tire des crises de l'actualité → scénarios quasi infinis.

## Pilier 2 — Le Théâtre (acquis + extensions ludiques)

Déjà là : Game Master LLM, négociation visible tour par tour (badges modèle + chrono), **Juge** (deltas bornés), communiqué G7, fog of war (`perception.py`), mémoire (`country_memory`), 3 rôles.

Extensions à fort rendement ludique :
- **Objectifs secrets + leaderboard** : chaque SI a des conditions de victoire cachées ; le Juge score la progression.
- **Conseil des super-intelligences** : la « plus haute instance » comme lieu nommé (Conseil de sécurité augmenté, ordre du jour, motions, veto). Suspense : coordination (utopie) ou **condominium** de 2-3 SI (dystopie) ?
- **Humain = le principal** : au lieu de « jouer un pays », l'humain joue le chef d'État qui tente de garder sa SI **alignée et en laisse**. « Peux-tu encore piloter ta super-intelligence ? » = la charnière utopie/dystopie, jouable.
- **Carte du monde animée**, **commentateur analyste** (⚠️ VRAM : petit modèle/API ou séquentiel), **rewind / what-if** (snapshot `WorldState`) — et les **particuliers parient** sur les négociations (marché, argent fictif).

## Pilier 3 — Le Marché de prédiction (la clé de voûte)

**L'idée.** Chaque round ouvre des **marchés** ; le **Juge est l'oracle de résolution**. Exemples :
- « L'Iran va-t-il condamner l'Arabie saoudite ce round ? » (action)
- « L'indice Utopie va-t-il monter ? » (trajectoire du monde)
- « Quelle SI gagne le Conseil ? » (arbitrage)
- « Un pacte USA–France sera-t-il formé ? » (diplomatie)

**Qui parie.** N'importe quel **particulier** (spectateur) mise sur une négociation en cours, aux côtés de **LLM-forecasters** (un modèle qui parie) — on compare qui prédit le mieux la super-intelligence.

**Mécanique (argent fictif / réputation).** Crédits virtuels ; cotes via pari mutuel simple ou **LMSR** (market maker automatique) ; P&L, **classement**, et **score de calibration (Brier)** par joueur et par modèle. Zéro argent réel.

**Pourquoi c'est la clé de voûte.** Parier sur les actions d'une SI, c'est *exactement* le sujet du projet : **mesurer la prévisibilité d'une intelligence supérieure**. Le marché unifie les trois besoins — **ludique** (enjeu, gagner/perdre), **réel** (résolution rigoureuse par le Juge), **recherche** (calibration = donnée publiable, écho direct aux résultats *LLMs as Strategic Actors* 2026).

**⚠️ Argent réel = hors scope.** Une version à mises réelles est une **activité régulée** (droit des jeux / dérivés selon juridiction ; Polymarket a connu des démêlés réglementaires). Elle exigerait une **revue juridique dédiée** — à traiter comme un projet séparé, pas un ajout au MVP. Le simulateur reste en **argent fictif**.

**Où ça se branche** *(local-first, léger)* :
- `market/` : `Market`, `Position`, cotes (LMSR), `resolve()` alimenté par le `RoundSummary` du Juge.
- Stockage : marchés / positions / P&L (Postgres ou SQLite au début).
- API : réutilise `app/` FastAPI (`/api/markets`, `/api/bet`).
- UI : un onglet **« Marché »** dans le théâtre Streamlit (marchés ouverts, mise, classement).

---

## Catalogue des mécaniques

Toutes les mécaniques (les 4 thèmes ludique × réel), leur **ancrage réel** et le **découpage Cowork ↔ Claude Code** sont détaillés dans **`docs/roadmap_features.md`** — chacune reliée à une référence : Kahn (escalade), Putnam (politique intérieure), Hanson/LMSR (marché), GDELT/ICB (crises), EIA/IEA (énergie), *Strategic Actors* 2026 (métriques).

## Garde-fous (cohérents avec l'existant)

Outil d'**analyse de signaux explicables**, pas un oracle. **Argent fictif** uniquement. **Fiction spéculative comme méthode**, pas de la prévision. Jamais de boucle de décision létale autonome. Limites documentées dans le `README.md` (« Limites & éthique »).

## Le one-liner

> *Un théâtre où des super-intelligences négocient l'avenir des États — et un marché où vous pariez sur ce qu'elles feront, pendant que le monde bascule vers l'utopie ou la dystopie.*

## Prochaines briques (mapping indicatif)

| Brique | Module | Sert |
|---|---|---|
| Indice de trajectoire Utopie–Dystopie | `simulation/trajectory.py` + Juge | Pilier 1 (le payoff) |
| Objectifs secrets + scoring | `agents/` + `agents/judge.py` | Piliers 2 & 3 |
| Marché de prédiction (argent fictif) | `market/` + `app/` + onglet UI | Pilier 3 (clé de voûte) |
| Conseil des super-intelligences | `simulation/council.py` | Pilier 2 (l'instance) |
| Humain = principal (alignement en laisse) | `agents/human_agent.py` + UI | Pilier 1 & 2 |
