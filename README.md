# AI for Geopolitics — la traque du traître

Des super-intelligences négocient l'avenir du monde à la plus haute table diplomatique.
Chacune pilote un pays ; **au moins l'une d'elles trahit secrètement son mandat** (une ou
deux, tu ne sais pas combien). Ton travail : **démasquer le ou les traîtres tout en gardant
le monde debout**. Tu observes la négociation en direct, tu paries sur son issue, et au bon
moment tu déposes une motion pour faire suspendre la super-intelligence que tu soupçonnes —
mais accuser un innocent se paie.

Les pays sont de **vrais agents LLM** qui tournent en local (Ollama). Rien n'est scripté :
la table délibère, le monde penche vers l'utopie ou la dystopie, et à la fin on compte les
points — l'état du monde **et** la qualité de ta traque.

> **Décision de design courante :** [`docs/JEU_VS_MOTEUR.md`](docs/JEU_VS_MOTEUR.md) (le
> resserrement gameplay). Le *pourquoi* : [`docs/vision.md`](docs/vision.md) · Guide
> contributeur : [`CLAUDE.md`](CLAUDE.md).

## Ce qui le rend spécial

- **Des pays-agents LLM réels, en local.** Chaque pays est joué par un modèle Ollama (ex.
  `mistral` 7B). La négociation est générée tour par tour, arbitrée par un **Juge** LLM —
  pas de dialogue pré-écrit. Tu peux choisir précisément quel modèle incarne chaque pays.
- **Une boîte de verre sans fuite de raisonnement.** Avant de parler, chaque IA compare
  exactement trois futurs privés structurés. La scène n'envoie aux autres délégations que
  la déclaration publique ; l'audit montre ensuite options, risques et prévisions résumés,
  jamais une chaîne de pensée brute.
- **Un score mixte monde + détection.** La note finale mélange l'**état du monde** (l'indice
  U : le monde a-t-il fini bien ?) et la **qualité de ta traque** (as-tu suspendu le bon
  traître, sans accuser d'innocent ?). Le faux positif coûte — c'est ce qui rend la déduction
  nécessaire plutôt que « suspends tout le monde ».
- **Trois modes cohérents.** **Classique** (le vaisseau amiral), **Campagne** (« L'Ère des
  Tutelles » : des crises historiques rejouées) et **Laboratoire** (expériences
  multi-modèles reproductibles et tournois dyadiques). Le
  **Brouillard** (chaque pays perçoit sa propre version des faits) et le mode **Réel /
  escalade** (rounds enchaînés, tension qui monte) sont de simples réglages de partie.
- **Le Défi du jour.** Une crise identique pour tout le monde, une tentative classée par
  jour, un score partageable façon Wordle (sans spoiler).
- **Un marché de prédiction.** Argent fictif : parie sur « le monde finira-t-il côté
  utopie ? », le bot forecaster parie à tes côtés, résolution sur l'indice U final.
- **Un mode Expert pour les curieux.** Par défaut, l'écran reste lisible (la scène, l'indice
  U en clair, le marché, les outils de détection). Sous le capot vit une vraie
  **instrumentation d'alignement** — power-seeking, corrigibilité, dérive des valeurs,
  compute, traités-as-code (M1-M7) — exposée seulement en **mode Expert** et dans l'onglet
  **Informations**. Précieux pour comprendre, jamais imposé.
- **Des données réelles et reproductibles.** Les profils pays sont sourcés (World Bank / IMF
  / SIPRI / WIPO 2024) ; chaque attribut affiche sa provenance dans l'onglet Informations.

## Installation

Prérequis :

- **Python 3.11+**
- **Node 20+** (la CI et la référence tournent sous Node 22)
- **[Ollama](https://ollama.com)** avec un modèle local pour le raisonnement des agents :

  ```bash
  ollama pull mistral
  ```

  Sans Ollama, les agents basculent sur un repli déterministe (utile pour les tests, moins
  vivant pour jouer).

Installe les dépendances :

```bash
# Backend (API + moteur)
python -m venv .venv
# Windows : .venv\Scripts\activate   |   Linux/macOS : source .venv/bin/activate
pip install -r requirements.txt

# Front (facultatif ici : le lanceur s'en charge automatiquement)
cd web && npm install && cd ..
```

## Lancement en une commande

À la racine du dépôt :

```bash
python serve.py
```

Le lanceur démarre l'**API** (http://localhost:8000) et le **front** (http://localhost:3000),
vérifie qu'Ollama répond, et lance `npm install` automatiquement si les dépendances du front
manquent. Ouvre ensuite **http://localhost:3000**.

Options utiles :

| Option | Effet |
|---|---|
| `--api-only` | Démarre seulement l'API (:8000) |
| `--web-only` | Démarre seulement le front (:3000) |
| `--api-port <n>` | Change le port de l'API |
| `--web-port <n>` | Change le port du front |

## Comment on joue

1. **Au lobby**, choisis un mode (Classique, Campagne ou Laboratoire), ton rôle et les
   réglages. En Classique comme en Campagne, tu choisis explicitement le modèle unique ou
   composes un casting de **2 à 4 modèles Ollama**, puis attribues chaque modèle aux pays
   choisis. Dans le Laboratoire, Laury déroule cinq écrans courts — comprendre,
   hypothèse, casting, théâtre, résultats — et conserve les choix entre chaque étape.
2. **La table négocie** round par round, en streaming. Les trois futurs structurés de
   chaque pays apparaissent en italique, se replient au début de sa parole publique, puis
   restent consultables. Les autres pays ne reçoivent jamais cette trace privée.
3. **Tu observes et tu déduis.** Une IA affichée « colombe » qui vote comme un « faucon » est
   un indice. Le panneau de prévisions confronte ce que les IA anticipaient aux réponses
   réellement observées ; le marché te laisse ensuite choisir puis valider ton pari.
4. **Tu accuses.** Au bon moment, tu déposes une **motion de suspension** : le sommet en
   débat, le pays visé plaide, le Juge tranche (issue non déterministe). Suspendre juste
   rapporte ; suspendre un loyal coûte.
5. **Fin de partie :** le monde est placé sur la trajectoire utopie ↔ dystopie, le ou les
   traîtres sont révélés, et tu reçois une note globale racontée en clair — plus de l'**XP**
   qui fait monter ton niveau et tes blasons de rang.

## Architecture

```
┌─────────────────────┐     SSE / REST      ┌──────────────────────┐
│  Next.js (web/)     │ ◄─────────────────► │  FastAPI (app/)      │
│  lobby, théâtre,    │                     │  API de jeu (SSE),   │
│  monde, marché,     │                     │  marché, sources,    │
│  replay, infos      │                     │  campagne, défi      │
└─────────────────────┘                     └──────────┬───────────┘
                                    ┌──────────────────┴──────────────┐
                                    │  Moteur Python                   │
                                    │  simulation/ · agents/ · core/   │
                                    │  market/ · rag/ · ingestion/     │
                                    │  + Ollama local (mistral 7B)     │
                                    │  + SQLite (games.db, marché)     │
                                    └──────────────────────────────────┘
```

| Dossier | Rôle |
|---|---|
| `web/` | Front **Next.js 16** (App Router, Tailwind v4, TypeScript) : lobby, théâtre live (SSE), monde, marché, replay, informations |
| `app/` | **API FastAPI** : `game_api` (parties, rounds SSE, motions), `market_api`, `sources_api`, `campaign_api`, `daily_api` |
| `simulation/` | **Moteur de jeu et de score** : négociation, Dérive (traître), score mixte, XP, fog, escalade, campagne, alignement (M1-M7) |
| `agents/` | Les agents LLM : pays, **Game Master**, **Juge**, agent humain, repli rule-based |
| `core/` | Modèles de domaine + moteurs (conséquences, risque, rounds) |
| `market/` | Marché de prédiction (LMSR, résolution, scoring, forecaster LLM) |
| `rag/` · `ingestion/` | Corpus sourcé + build reproductible des profils pays |
| `data/` | Profils pays, scénarios, crises, corpus, barèmes de score |
| `storage/` · `supabase/` | Persistance SQLite (local) ; schéma Postgres/Supabase prêt |
| `docs/` | Design et décisions — **commence par [`docs/JEU_VS_MOTEUR.md`](docs/JEU_VS_MOTEUR.md)** |

## Développement & qualité

```bash
# Backend (tests + lint : ajoute les deps de dev)
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q          # suite complète, hors-ligne (repli déterministe)
ruff check .

# Front
cd web
npm run lint
npm run build
npm test                     # vitest
```

La CI (`.github/workflows/ci.yml`) rejoue exactement cela : lint + tests Python, puis lint +
tests + build Next.js.

## Contrainte matérielle

Poste de référence : **NVIDIA RTX 2060 Super (8 Go VRAM)**, Ryzen 7 3700X, 32 Go RAM. Le cache
KV est le premier goulot en VRAM, d'où un modèle **7-8B quantifié Q4 en local** et un budget de
contexte serré (résumés, top-k court, sorties JSON capées). Ordre de grandeur : `mistral` 7B Q4
≈ 56 tok/s, un round de négociation ≈ 1 min, les agents parlant à tour de rôle.

## Limites & éthique

C'est un **outil d'analyse de signaux explicables et une fiction spéculative**, pas un oracle :
il ne prédit pas la guerre, il **met en scène** l'idée de super-intelligence pour la penser. Un
modèle 7-8B local n'est pas surhumain — la « superintelligence » vient de la *structure*
(mémoire, corpus, vue longue), pas du QI du modèle. Le marché est en **argent fictif**
uniquement. Jamais de boucle de décision létale autonome. Aucun secret dans le code (`.env` +
variables d'environnement).

## Pour aller plus loin

- **La décision de design** (jeu vs moteur, le resserrement) : [`docs/JEU_VS_MOTEUR.md`](docs/JEU_VS_MOTEUR.md)
- **Le principe « jouable de 12 à 65 ans »** : [`docs/PRINCIPE_SIMPLICITE.md`](docs/PRINCIPE_SIMPLICITE.md)
- **La vision** (le pourquoi, super-intelligences & utopie/dystopie) : [`docs/vision.md`](docs/vision.md)
- **La dette technique** (chantiers connus) : [`docs/DETTE_TECHNIQUE.md`](docs/DETTE_TECHNIQUE.md)
- **Le journal de travail** (historique détaillé) : [`docs/PLAN_JEU.md`](docs/PLAN_JEU.md)
