# web/ — Théâtre des super-intelligences (Phase R3)

Front **Next.js (App Router) + Tailwind, TypeScript**, branché sur l'API de jeu R1
(`app/game_api.py`). Trois écrans :

- **Lobby** (`/`) — créer une partie (`POST /api/games`), retrouver les parties vivantes
  ou en relecture seule (`GET /api/games`).
- **Théâtre live** (`/games/{id}`) — le round streamé en SSE depuis
  `POST /api/games/{id}/rounds` : événement du GM, prises de parole des
  super-intelligences token par token (réflexion privée repliable), délibéré du juge,
  verdict, communiqué, risque, trajectoire Utopie–Dystopie.
- **Replay** (`/games/{id}/replay`) — relecture ordonnée depuis `GET /api/games/{id}`
  (table `transcripts`), avec « lecture théâtre » progressive. C'est le futur mode démo
  public (Phase R5).

## Lancer en local

1. **Backend** (depuis la racine du repo, venv actif) — persister les parties dans un
   fichier pour que le replay survive aux redémarrages :

   ```powershell
   $env:GAME_DB_PATH = "games.db"
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
- **Le flux peut se couper sans événement de fin** (exception moteur, redémarrage
  d'uvicorn) : le client le détecte (`done` jamais reçu), affiche une bannière et
  resynchronise l'historique via `GET /api/games/{id}` — l'UI ne pend jamais.
- Un `409` (round déjà en cours, ou session process perdue) est montré tel quel avec
  l'action de repli (replay).
- Événement inconnu dans le flux (nouveau `RoundStep` côté moteur) : ignoré sans casser
  le théâtre.
