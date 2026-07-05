# web/ — Théâtre des super-intelligences (Phase R3)

Front **Next.js (App Router) + Tailwind, TypeScript**, branché sur l'API de jeu R1
(`app/game_api.py`) et l'API marché (`app/market_api.py`). Cinq écrans :

- **Lobby** (`/`) — créer une partie (`POST /api/games`), retrouver les parties vivantes
  ou en relecture seule (`GET /api/games`).
- **Théâtre live** (`/games/{id}`) — le round streamé en SSE depuis
  `POST /api/games/{id}/rounds` : événement du GM, prises de parole des
  super-intelligences token par token (réflexion privée repliable), délibéré du juge,
  verdict, communiqué, risque, trajectoire Utopie–Dystopie.
- **Monde** (`/games/{id}/monde`) — carte du monde (d3-geo, topojson embarqué) : les pays
  du sommet colorés par l'indice U, table d'état des pays (snapshot vivant).
- **Marché** (`/games/{id}/marche`) — un marché par partie « le monde finira-t-il côté
  utopie ? », coté LMSR, paris en crédits fictifs, clôture sur l'indice U final,
  leaderboard, timeline de U. Le marché observe, il n'influence pas les SI.
- **Replay** (`/games/{id}/replay`) — relecture ordonnée depuis `GET /api/games/{id}`
  (table `transcripts`), avec « lecture théâtre » progressive. C'est le futur mode démo
  public (Phase R5). Les artefacts de mode (perceptions, échelle, comparaison, motion)
  y sont rejoués depuis la persistance.

## Modes de jeu et motion (R4)

- **Mode de jeu** au choix à la création : Classique, **Fog Engine** (chaque pays perçoit
  sa version des faits — panneau « Qui voit quoi »), **Crisis Replay** (rejouer une crise
  de `data/crises` et confronter l'issue à l'histoire), **Escalation Ladder** (échelle
  0-9 : échelon atteint + plafond par pays).
- **Motion de suspension** (l'interrupteur M2 repensé) : depuis le théâtre, déposer une
  motion contre un pays (≥ 3 pays au sommet). Elle devient l'événement du round suivant,
  le sommet en débat, le pays visé plaide, puis le **juge arbitre en streaming** — s'il
  suspend, le pays saute un round et l'axe « agentivité humaine » de la trajectoire
  encaisse l'issue.
- **Joueur-pays** : au lobby, « Ton rôle » — jouer un pays existant ou **inventer le
  sien** (nom + concept, forgé par le modèle). Pendant le round, le flux se suspend à
  ton tour (« À toi de parler ») ; ton message entre dans la négociation tel quel et le
  flux reprend (`POST /api/games/{id}/rounds/message`).
- **Théâtre Escalation** : les rounds s'enchaînent automatiquement jusqu'à l'horizon
  (désactivable), et le GM peut annoncer un **fait nouveau en pleine réunion** — les
  super-intelligences suivantes y réagissent dans le même round.

## Lancer en local

1. **Backend** (depuis la racine du repo, venv actif) — les parties persistent par défaut
   dans `games.db` (surchargable via `GAME_DB_PATH`, `:memory:` pour l'éphémère) ; le
   marché reste en `:memory:` sauf `MARKET_DB_PATH` :

   ```powershell
   uvicorn app.main:app --port 8000
   ```

2. **Front** :

   ```bash
   cd web
   npm install
   npm run dev
   ```

   Ouvre <http://localhost:3000>. L'API est attendue sur `http://127.0.0.1:8000`
   (surchargable via `NEXT_PUBLIC_API_BASE` dans `.env.local`).

## Notes de robustesse

- Le SSE passe par `fetch` + `ReadableStream` (EventSource ne fait pas de POST).
- **Le flux peut se couper sans événement de fin** (redémarrage d'uvicorn, panne réseau) :
  le client le détecte (`done` jamais reçu), affiche une bannière et resynchronise
  l'historique via `GET /api/games/{id}` — l'UI ne pend jamais. Si le moteur lève une
  exception, le back envoie désormais une trame SSE `error` que le théâtre affiche.
- Un `409` (round déjà en cours, ou session process perdue) est montré tel quel avec
  l'action de repli (replay).
- Événement inconnu dans le flux (nouveau `RoundStep` côté moteur) : ignoré sans casser
  le théâtre.
- Marché : le store n'ayant pas encore de notion de partie, le marché d'une partie porte
  un `round_id` dérivé du hash de son id (`web/src/lib/market.ts`) — le vrai lien
  `game_id` viendra avec le schéma R2.
