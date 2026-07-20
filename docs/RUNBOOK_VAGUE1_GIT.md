# Runbook Vague 1 — partie git (à exécuter dans Claude Code)

> **Contexte.** Cowork (session cloud du 20/07) a appliqué les correctifs de code de la Vague 1
> directement dans le working tree et les a validés dans un sandbox propre : **208 tests ciblés
> verts** (dont 3 nouveaux tests de non-régression), **337 vitest verts, tsc 0 erreur, eslint 0,
> ruff 0**. Ce runbook couvre ce que le pont cloud ne peut pas faire proprement : les opérations
> git. À dérouler dans l'ordre. Réf. générale : `docs/ETAT_DE_LART_PROJET_2026-07.md` §7.

## Ce qui a été modifié par Cowork (à committer ici)

| Fichier | Correctif |
|---|---|
| `pyproject.toml` | packaging : `research*` ajouté à `packages.find` (pip install -e . complet) |
| `Dockerfile` | `COPY research/` (l'image ne cassait plus silencieusement au démarrage) |
| `.github/workflows/ci.yml` | ⚠️ **NON écrit** (fichier protégé pour le pont cloud) — à appliquer À LA MAIN, voir Étape 0-bis |
| `supabase/schema.sql` | colonne `extras_json` + ALTER idempotent (parité avec SQLite) |
| `storage/game_store.py` | `SessionSnapshot.extras` (colonne + migration + save/get) — réceptacle additif : turn_seconds, suspended_rounds, free_briefs_* |
| `storage/supabase_store.py` | extras_json (save/get) |
| `app/game_api.py` | ① `ranked` exclut `expose_thinking` (exploit du Défi classé) ② plus JAMAIS de snapshot sous verrou (`verify`/`file_motion` en plein round) ③ actes de Dérive filtrés par pays actifs (un banc n'a pas d'actes ni de vote) ④ extras persistés/restaurés (turn_seconds, suspended_rounds, free_briefs) ⑤ la deadline RÉCLAME le tour/le bulletin sous verrou → un POST tardif reçoit 409 explicite au lieu d'un « accepted » perdu |
| `app/main.py` | repli `MAX_CONCURRENT_SIMULATIONS` invalide : 8 → 1 (cohérent mono-GPU) |
| `tests/test_game_api.py` | +3 tests : compteur de suspension survit au restart · extras survivent · expose_thinking déclasse |
| `tests/test_motions.py` | E501 (ligne coupée) |
| `web/src/lib/game-phase.ts` | accents de `phaseLabel` (« Le sommet est prêt », …) |
| `web/src/components/theatre/action-dock.tsx` | bouton **Resynchroniser** en phase `disconnected`/`error` (prop `onResync`) |
| `web/src/app/games/[id]/page.tsx` | câblage `onResync={resync}` |
| `.gitattributes` | **nouveau** — police de fins de ligne (base de l'étape 3) |

Correction vs l'état de l'art : les « 8 erreurs ruff I001 » étaient un artefact d'analyse (sans
`research/` dans l'arbre, ruff classait ces imports en tiers) — seule l'E501 était réelle, corrigée.
Note : une session Claude Code a modifié `app/campaign_api.py`, `web/src/lib/types.ts`,
`tests/test_research_lab.py` et créé `PR_BODY.md` vers 12h43-12h53 — aucun chevauchement avec les
fichiers ci-dessus ; intègre-les dans tes commits comme il se doit.

## Étape 0 — état des lieux

```bash
git status                                   # attendu : ~430 fichiers M (bruit EOL) + les fichiers ci-dessus
git diff --stat --ignore-cr-at-eol           # les VRAIS changements, bruit EOL ignoré — relis-les
```

Deux réparations déjà faites côté Cowork, pour info : l'`index.lock` orphelin a été déplacé vers
`AI_Geopolitcs/_to_delete/` (git refonctionne), et une archive d'analyse `_etat_source.tgz` y a
été rangée aussi (dossier `_to_delete/` supprimable à la main).

## Étape 0-bis — patch CI à appliquer à la main (fichier protégé)

Les workflows GitHub ne sont pas modifiables via le pont cloud. Dans
`.github/workflows/ci.yml`, remplacer :

```yaml
      - name: Installer le projet + outils
        run: pip install -e ".[ui]" pytest ruff
```

par :

```yaml
      - name: Installer le projet + outils
        # L'extra "[ui]" n'existe plus (supprimé par CLEANUP-B) : requirements-dev
        # porte pytest + ruff, la source canonique des versions.
        run: pip install -e . -r requirements-dev.txt
```

## Étape 1 — valider localement AVANT de committer

```bash
python -m pytest -q            # suite complète : verte, ~10-12 min (2 tests attendent ~3 min d'horloge réelle)
ruff check .                   # attendu : All checks passed
cd web && npm test && npx tsc --noEmit && npm run lint && cd ..
```

## Étape 2 — committer les vrais changements (commits atomiques)

Suggestion de découpage (adapte à ce que `git diff --ignore-cr-at-eol` montre d'autre) :

```bash
git add pyproject.toml Dockerfile .github/workflows/ci.yml
git commit -m "fix(packaging): research* dans packages.find + Dockerfile + CI sans extra mort"

git add storage/game_store.py storage/supabase_store.py supabase/schema.sql app/game_api.py tests/test_game_api.py
git commit -m "fix(persistance): SessionSnapshot.extras (turn_seconds, suspension pluri-rounds, briefs) + jamais de snapshot sous verrou"

git add app/game_api.py  # si hunks restants : réclamation du tour + drift acts + ranked
git commit -m "fix(moteur): deadline reclame le tour (409 tardif), actes de Dérive des pays actifs seulement, expose_thinking declasse"

git add app/main.py tests/test_motions.py web/src/lib/game-phase.ts web/src/components/theatre/action-dock.tsx "web/src/app/games/[id]/page.tsx"
git commit -m "fix(divers): repli mono-GPU coherent, E501, accents phaseLabel, CTA Resynchroniser"
```

## Étape 3 — normalisation des fins de ligne (le `.gitattributes` est déjà posé)

```bash
git config core.autocrlf false
git add .gitattributes
git add --renormalize .
git status                     # tout le bruit EOL est maintenant DANS ce commit unique
git commit -m "chore: normalize line endings via .gitattributes"
```

À partir d'ici, `git diff` redevient lisible. Pour les branches pas encore fusionnées :
`git merge -X renormalize <branche>`.

## Étape 4 — nettoyage des branches / worktrees (avec preuve de fusion)

```bash
git worktree list
git branch -a
# Pour CHAQUE branche candidate (chore/cleanup-a..e, cleanup-integration, db-maintenance,
# feat/brief-3, feat/brief-4, codex/refonte-ui-laboratoire) :
git cherry -v feat/briefs-gameplay-6pts <branche>   # aucune ligne "+" = contenu déjà intégré
# Si intégrée :
git worktree remove <chemin-du-worktree>
git branch -d <branche>
```

Puis décider du sort de `feat/briefs-gameplay-6pts` elle-même : merge vers `main` (ou la branche
principale du dépôt) + tag, ou continuer dessus. `PR_BODY.md` à la racine suggère qu'une PR est
déjà en préparation — réutilise-le.

## Étape 5 — pousser et vérifier la CI

La CI doit passer telle quelle (lint + pytest offline + front). **Ne pas ajouter
`ruff format --check`** pour l'instant : 98 fichiers seraient à reformater — si tu veux cette
garde, fais un commit de reformatage dédié (`ruff format .`) APRÈS la normalisation EOL, en
décision séparée.

## Reste à faire (suite de la Vague 1, côté Claude Code)

1. **Test manquant — actes de Dérive filtrés** : en Dérive, après une motion retenue contre un
   traître, vérifier que le round suivant n'enregistre AUCUN acte (`judge_json["drift"]["acts"]`)
   pour le pays au banc, ni de consigne de vote. Fixture : `suspend_happy_client` de
   `tests/test_drift_api.py`.
2. **Horloge injectable pour `PendingTurn`/`PendingMotionVote`** : remplacer `time.time()` par un
   `now` injectable (module-level monkeypatchable) — permet de tester la course POST/deadline en
   déterministe ET d'accélérer la suite (~6 min gagnées : `test_xp_credited_once…` et
   `test_tutorial_chapter` attendent ~3 min d'horloge réelle chacun).
3. Enchaîner sur la **Vague 2** (fenêtre de pensée en direct) : design complet dans
   `docs/ETAT_DE_LART_PROJET_2026-07.md` §4.
