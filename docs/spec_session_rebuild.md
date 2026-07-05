# Spec — Reconstruction de session au restart

> Décisions de conception (Cowork, juillet 2026). Implémentation : une session Claude Code,
> après merge de R2 (le snapshot vit dans le `GameStore`, quelle que soit l'implémentation).

## Problème

La partie vivante (`GameSession` : monde, agents, GM, juge, horloge, mode, motion en attente,
suspendus, `recent`) n'existe qu'en mémoire process. Au restart d'uvicorn, la partie passe en
« relecture seule » (409 sur `POST /rounds`), même si `games.db` a tout l'historique.

## Décisions

**1. Snapshot après chaque round, dans le store.**
À la fin de `_play_round` (après `add_round`/`add_transcript`), upsert d'une ligne
`game_sessions` : `world_json` (`WorldState.model_dump(mode="json")`), `clock_json`,
`recent_json`, `pending_motion_json`, `suspended_json`. Nouveau contrat `GameStore` :
`save_session_snapshot(game_id, snapshot)` / `get_session_snapshot(game_id)`
(SQLite : table alignée sur `supabase/schema.sql`; Supabase : la même).
Snapshot aussi à la création de partie (round 0), sinon une partie jamais jouée
n'est pas reconstructible. **Et à chaque `POST /motions`** (revue Claude Code) : la motion
mute la session entre deux rounds — sans upsert à ce moment-là, le test « restart avec
motion en attente » ci-dessous ne peut pas passer.

**2. Reconstruction paresseuse, au premier besoin.**
Pas de rechargement au boot. Là où le code fait `_sessions.get(game_id)` et répondrait
409/relecture (`POST /rounds`, `POST /motions`), tenter d'abord `_rebuild_session(game_id)` :

- `world = WorldState.model_validate(snapshot.world_json)`
- `agents = {cid: LLMAgent(cid, backend) for cid in world.countries}` — **agents recréés
  à froid** (décision : leur contexte vient du monde + `recent`; la mémoire conversationnelle
  interne éventuelle est perdue, c'est accepté et documenté)
- GM, juge : recréés (stateless entre rounds)
- `clock` : restauré depuis `clock_json`
- `mode` : depuis `games.mode` (colonne R4)
- `recent`, `pending_motion`, `suspended` : depuis le snapshot
- La session reconstruite entre dans `_sessions` avec un verrou neuf.

**3. `live` devient trois états côté API.**
`GameView.live: bool` → conservé pour compat, mais ajouter `resumable: bool`
(snapshot présent et `status = running`). Le front peut alors afficher
« Reprendre la partie » au lieu de « relecture seule ». Échec de reconstruction
(snapshot absent/invalide, partie `finished`) → comportement actuel inchangé (relecture).
Option à coût nul (revue Claude Code) : `GET /games/{id}` peut servir `world` depuis
`world_json` quand la session process est absente — la page Monde retrouve l'état des
pays après restart sans reconstruire d'agents.

**4. Ce qu'on ne reconstruit PAS.**
Un round interrompu en plein stream n'est pas repris : il est perdu (le snapshot est
pré-round, l'état du monde n'a pas été muté durablement — le client rejoue le round).
Le backend d'inférence n'est pas snapshoté (config process). Les comptes marché vivent
déjà dans leur propre store.

## Tests attendus

- Créer partie → jouer 1 round → simuler restart (vider `_sessions`) → `POST /rounds`
  reconstruit et joue le round 2 ; le round 2 référence bien le monde muté du round 1.
- Restart avec motion en attente → la motion est débattue au round suivant.
- Partie `finished` ou sans snapshot → 409 relecture seule (inchangé).
- Mode `escalation`/`fog` : le mode survit au restart (colonne `games.mode`).
