# Plan de refonte — Streamlit → Next.js + FastAPI + Supabase

> Décisions actées (juillet 2026) : **local d'abord** (Ollama conservé), architecture prête pour un
> déploiement Vercel ultérieur (mode démo/replay pour les visiteurs tant que l'inférence reste locale).

## Architecture cible

```
┌─────────────────────┐     SSE / REST      ┌──────────────────────┐
│  Next.js (web/)     │ ◄─────────────────► │  FastAPI (app/)      │
│  théâtre live, carte│                     │  moteur Python       │
│  marché, leaderboard│                     │  existant, inchangé  │
│  Vercel (plus tard) │                     │  local (uvicorn)     │
└─────────┬───────────┘                     └──────────┬───────────┘
          │                                            │
          │              ┌──────────────┐              │
          └────────────► │   Supabase   │ ◄────────────┘
                         │  Postgres    │        ┌────────────────┐
                         │  parties,    │        │ Ollama local   │
                         │  transcripts,│        │ (GPU, inchangé)│
                         │  marché, auth│        └────────────────┘
                         └──────────────┘
```

## Principes

- Le moteur Python (`core/`, `simulation/`, `agents/`, `market/`, `rag/`, `inference/`) **ne change pas**.
- `ui/app.py` (Streamlit) est remplacé **progressivement** ; on le garde jusqu'à parité.
- Tout l'état qui vivait dans `st.session_state` migre vers une persistance durable (Supabase à terme).
- L'abstraction `InferenceBackend` existante permet de basculer Ollama → API cloud plus tard sans
  toucher au reste.

## Phases

### Phase R1 — API de jeu (FastAPI)

Étendre `app/` avec les endpoints que le front consommera :

- `POST /api/games` — créer une partie (scénario, pays actifs, horizon).
- `POST /api/games/{id}/rounds` — jouer un round ; réponse en **SSE** (`text/event-stream`) qui
  streame : événement GM → tours de négociation par pays (tokens) → verdict du juge → deltas/risque.
- `GET /api/games/{id}` — état complet (monde, historique, transcript).
- Réutiliser l'API market existante (`app/market_api.py`) telle quelle.
- Persistance : chaque round écrit dans un `GameStore` (interface, cf. R2) — implémentation SQLite
  en local, Supabase/Postgres au déploiement.
- Tests : style des tests existants (TestClient httpx, MockBackend).

**Notes d'implémentation (R1 faite)** :

- Le flux SSE réutilise le générateur `run_negotiation_round` (`simulation/live_round.py`) tel quel :
  chaque `RoundStep` devient un événement SSE (`event: <type>\ndata: <json>`), nommé d'après la
  dataclass (`TurnStartStep` → `turn_start`, `TokenStep` → `token`, …), plus un `done` final.
- La partie vivante (monde + agents + horloge) reste **en mémoire process** (`app/game_api.py`) ;
  ce qui est durable (parties, rounds, transcripts) passe par `storage/game_store.py`
  (`GameStore` Protocol + `SQLiteGameStore`, même patron que `market/store.py`). La bascule Supabase
  = une nouvelle implémentation du Protocol, l'API ne bouge pas.
- Le transcript persiste aussi les prises de parole du **GM** (`speaker="gm"`) et du **juge**
  (`speaker="judge"`) : le théâtre rejouable est la simple relecture ordonnée de la table.

### Phase R2 — Schéma Supabase

Tables minimales :

- `games` (id, scenario, horizon, created_at, status)
- `rounds` (id, game_id, round_no, event_json, deltas_json, risk_json, judge_json,
  trajectory_json — ajout R1 : l'indice U est le cœur du jeu, il doit survivre au restart)
- `transcripts` (id, round_id, seq, speaker, model, content, reasoning, ts) — le théâtre rejouable
  (reasoning — ajout R1 : la « réflexion privée » fait partie du théâtre)
- `market_accounts`, `markets`, `trades` — migration du store in-memory de `market/store.py`
- Auth Supabase : optionnelle en local, prête pour le déploiement.

**Notes (schéma écrit)** : `supabase/schema.sql` — prêt à coller dans Supabase Studio.
Ajouts : `markets.game_id` (vrai lien partie↔marché, remplace le `round_id` dérivé du hash
côté front — note R3), RLS lecture publique sur le théâtre/marché (cible replay public R5),
soldes (`market_accounts`/`positions`) non exposés. L'implémentation Python =
`SupabaseGameStore` + `SupabaseMarketStore` derrière les Protocols existants.

### Phase R3 — Front Next.js (`web/`)

- Next.js App Router + Tailwind (+ shadcn/ui), TypeScript.
- Pages : **Théâtre live** (streaming SSE, badges modèle, chrono — parité avec l'existant),
  **Monde** (carte choroplèthe, état des pays), **Marché** (cotes LMSR, paris, leaderboard),
  **Replay** (relecture d'une partie depuis `transcripts` — servira de mode démo public).
- Utiliser le skill `ui-ux-pro-max` pour la direction artistique.

**Notes d'implémentation (R3 faite — lobby, théâtre, monde, marché, replay)** :

- `web/` : Next.js 16 (App Router, Turbopack) + Tailwind v4, TypeScript. Pas de shadcn/ui à ce
  stade (kit UI maison plus léger) ; DA « dark OLED, accent or spotlight » générée via
  ui-ux-pro-max, tokens CSS dans `globals.css`.
- Cinq écrans : **lobby** `/` (créer/lister les parties), **théâtre live** `/games/{id}`
  (round streamé), **monde** `/games/{id}/monde` (carte d3-geo/topojson embarqué, pays du
  sommet colorés par U + table d'état des pays), **marché** `/games/{id}/marche` (un marché
  LMSR par partie « utopie finale ? », paris fictifs, clôture sur U final, leaderboard,
  timeline de U — branché sur `app/market_api.py` inchangé ; lien partie↔marché = `round_id`
  dérivé du hash de la partie en attendant R2), **replay** `/games/{id}/replay` (relecture
  ordonnée des `transcripts`, avec « lecture théâtre » progressive).
- SSE en `fetch` + `ReadableStream` (EventSource ne fait pas de POST) : parseur dans
  `web/src/lib/sse.ts`, réduction en état affichable dans `web/src/hooks/useRoundStream.ts`.
  **Le flux peut se couper sans `done`** (restart uvicorn, réseau) : le client le détecte,
  affiche une bannière et resynchronise via `GET /api/games/{id}` — vérifié en tuant
  uvicorn en plein round. Événement SSE inconnu = ignoré (compatible avec de futurs RoundStep).
- Changements Python (retouches de revue R1 comprises) : middleware **CORS** dans
  `app/main.py` (front :3000 → API :8000) ; `GAME_DB_PATH` par défaut = **`games.db`**
  (la relecture survit aux restarts — les parties passent en « relecture seule ») ;
  trame SSE **`error`** si le moteur lève en plein round (plus de coupure muette) ;
  `GeoEvent` humain construit dans le `try` de `_play_round` (verrou toujours relâché).

### Phase R4 — Parité utile, bascule et nettoyage

**Périmètre acté (juillet 2026)** — migre vers le web : Fog/Crisis/Escalation (le cœur
dramatique) et l'interrupteur M2 **repensé** (ci-dessous). Backlog (restent en Streamlit
legacy pour l'instant) : invention de pays (country_forge), radar M3, budget LLM.

**Interrupteur M2 repensé — « motion de suspension » arbitrée** :

- L'humain n'exclut plus un pays par du code : il dépose une **motion de suspension**
  contre un pays (bouton pause/exclusion du théâtre).
- La motion est injectée dans le round comme événement (« motion de suspension déposée
  contre X, motif : … ») ; les autres pays **en débattent** pendant la négociation,
  le pays visé peut plaider sa cause.
- Le **juge arbitre** en fin de round (suspendre ou non, raisonnement streamé) — issue
  non déterministe. S'il suspend, le pays saute le round suivant ; le théâtre montre
  la réaction (tension, alliances, indice U).
- Côté API : `POST /api/games/{id}/motions` (pays visé + motif) → la motion entre dans
  le prochain round ; le verdict du juge inclut `suspension: {country, upheld, reasoning}`.

**Notes d'implémentation (R4 faite — motion + Fog/Crisis/Escalation web)** :

- **Motion** : `simulation/motions.py` (Motion, `motion_event` — **tout le sommet est
  acteur** de la motion, sinon l'heuristique d'engagement laisse les non-visés muets,
  constaté sur mistral réel ; prompt d'arbitrage avec **verdict demandé en tête** de
  réponse + `parse_motion_verdict` sur la première phrase du dernier marqueur
  `VERDICT:` — négation/rejet prioritaires sur le mot « suspendre », durci sur une
  sortie mistral réelle qui inversait l'issue ; repli = rejet) ;
  `run_negotiation_round(motion=…)` streame l'arbitrage (`MotionTokenStep` →
  `MotionVerdictStep`) après le communiqué, puis la trajectoire encaisse l'issue sur
  **A2** via `nudge_axis` (confirmée : A2 ↑ cap 0,03 ; rejetée : A2 ↓ cap 0,02 ;
  explication du round conservée).
  Suspension = le pays saute **un** round (retiré des agents du round suivant, trame SSE
  `suspended`) ; il faut ≥ 3 pays pour déposer une motion ; une motion à la fois ;
  la motion en attente **est** l'événement du prochain round (400 si event/fog/crise).
- **Modes** : `POST /api/games` prend `mode` (classic|fog|crisis|escalation), stocké sur la
  session ; `GET /api/library` liste `data/fog` + `data/crises`. Par round :
  `fog_id`/`fog` humain (perceptions par pays → trame `perceptions`), `crisis_id`
  (événement de la crise + `compare_outcome` → trame `comparison`), mode escalation →
  trame `ladder` (échelon atteint + plafonds par pays). Fonctions moteur **pures
  réutilisées telles quelles** ; artefacts persistés dans `judge_json` (formalisation
  en colonnes = R2/Supabase). Moteur inchangé sauf ajouts (motions, steps).
- **Front** : sélecteur de mode au lobby ; théâtre : dépôt de motion (bouton + formulaire),
  bannières motion en attente / pays au banc, panneau d'arbitrage streamé, sélecteurs de
  scénario fog / crise, panneaux « Qui voit quoi » (désinformé = croyance hors des vrais
  acteurs), « Échelle d'escalade » (0-9 par pays), « Simulation vs histoire » ; replay :
  les mêmes panneaux depuis `judge_json`. Vérifié live sur MockBackend (motion confirmée →
  round sans le pays → retour ; fog ; crise ; échelle).
- Reste de R4 (après validation de la parité par l'user) : archivage `ui/app.py` →
  `legacy/`, README racine, CI (pytest + build Next).

- Parité validée → `ui/app.py` archivé (`legacy/`), README mis à jour.
- CI : lancer les tests Python + build Next.js.

### Phase R5 (plus tard) — Déploiement

- Front sur Vercel, mode replay/démo public (aucun besoin de GPU).
- Backend : reste local, ou Fly.io/Railway si un jour l'inférence passe en API cloud.

## Répartition Cowork ↔ Claude Code

- **Cowork** : plan, schéma Supabase, specs, revues, documents, petites éditions.
- **Claude Code** : implémentation des phases R1 et R3 (grosses sessions de code). Prompts de
  démarrage suggérés :
  - R1 : « Lis docs/REFONTE_PLAN.md. Implémente la Phase R1 (API de jeu SSE) en réutilisant le
    moteur existant, avec tests sur MockBackend. Ne modifie pas core/ ni simulation/. »
  - R3 : « Lis docs/REFONTE_PLAN.md. Crée l'app Next.js dans web/ (Phase R3), page Théâtre live
    branchée sur l'endpoint SSE de R1. Utilise le skill ui-ux-pro-max pour le design. »

## Ce qui ne change pas

Ollama + RTX 2060 (inférence), tout le moteur Python, les données (`data/`), les tests existants,
le pipeline d'ingestion. La refonte est **additive** jusqu'à la Phase R4.
