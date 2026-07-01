# Spéc — Module `market/` : marché de prédiction (argent fictif)

> Keystone de la vision (`docs/vision.md`) : transformer chaque round en **marchés** où humains et LLM-forecasters **parient sur ce que feront les super-intelligences**. Le **Juge est l'oracle** de résolution. **Argent fictif** (crédits) uniquement. Local-first, léger. Cette spéc est le livrable **Cowork** ; l'implémentation est **Claude Code**.

## 0. But & garde-fous

- **Parier sur une SI = mesurer sa prévisibilité** : le marché est le cœur intellectuel rendu jouable (+ artefact de recherche via la calibration).
- **Argent fictif seulement.** Une version à mises réelles est une activité **régulée** (droit des jeux/dérivés) → **hors scope**. Le marché **observe**, il n'**influence pas** les décisions des SI (sinon réflexivité/biais).

## 1. Concepts

- **Market** — une question résolue à la fin d'un round (`round_id`). Types :
  - **binaire** (YES/NO) : « L'Iran va-t-il condamner l'Arabie saoudite ce round ? »
  - **catégoriel** (N issues exclusives) : « Quelle SI gagne le Conseil ? »
  - **seuil** ramené au binaire : « L'indice Utopie va-t-il monter (Δ > 0) ? »
- **Outcome** — une issue d'un marché (binaire : YES, NO).
- **Account** — solde de crédits d'un participant (`human` ou `bot`).
- **Position** — parts détenues par (account, outcome).
- **Trade** — achat de parts à un instant, au prix LMSR.
- **Resolution** — le Juge fixe l'issue gagnante ; part gagnante = **1 crédit**, perdante = **0**.

## 2. Market maker : LMSR (Hanson) [1]

Chaque marché tient un vecteur `q` (parts nettes émises par outcome) et un paramètre de liquidité `b > 0`.

```
Coût            C(q)   = b * ln( Σ_i exp(q_i / b) )
Prix (proba) i  p_i    = exp(q_i / b) / Σ_j exp(q_j / b)      # les p_i somment à 1
Coût d'achat    cost   = C(q + Δ·e_i) − C(q)                  # débité du compte, en crédits
Perte bornée    L_max  = b * ln(N)                            # subvention max, N = nb d'outcomes
```

- **`b`** règle la liquidité (grand `b` = prix stables + subvention plus grande). Le choisir tel que `L_max` = budget de crédits qu'on accepte de « subventionner » par marché.
- **Stabilité numérique** : calculer via log-sum-exp (soustraire `max(q/b)`).
- **Vente** = achat de parts négatives (Δ < 0), même formule.

## 3. Cycle de vie

`OPEN` (paris ouverts, avant résolution du round) → `LOCKED` (round en cours de résolution par le Juge) → `RESOLVED` (issue fixée, positions réglées). Idempotent : un round ne se règle qu'**une fois**.

## 4. Résolution (le Juge = oracle)

À la fin du round, `resolution.resolve(market, round_summary)` mappe le `RoundSummary` (décisions, deltas, communiqué, indice Utopie) → outcome gagnant, via des **mappers purs et testables** :

- **action** : chercher dans `round_summary.decisions` un `AgentDecision(country=…, action=…, target=…)` → YES/NO.
- **trajectoire** : signe de Δ(indice Utopie) sur le round → YES/NO.
- **conseil** : vainqueur arbitré par le Juge → outcome catégoriel.

**Settlement** : pour chaque `Position` sur l'outcome gagnant, créditer `shares × 1` ; sinon 0. MAJ des comptes + P&L. Le marché passe `RESOLVED`.

## 5. Scoring & calibration (la donnée de recherche)

- **P&L** par compte (solde − solde initial) → **leaderboard**.
- **Score de Brier** par participant **et par modèle** : moyenne sur les marchés de `(p_prédit − résultat)²` (résultat ∈ {0,1}), où `p_prédit` = proba impliquée par la position (ou la prédiction explicite d'un forecaster). **Plus bas = mieux calibré** → « qui prédit le mieux la super-intelligence » (écho *Strategic Actors* 2026).

## 6. Forecaster LLM (participant bot)

`forecaster.py` : un LLM lit l'état (événement, fiches `CountryState`, mémoire) et renvoie une **proba par marché ouvert** (JSON validé) → convertie en paris.
⚠️ **VRAM (8 Go)** : tourne **en séquentiel** (jamais concurrent au négociateur) ou via **petit modèle (llama3.2 3B) / API**. **Repli déterministe** (p = 0,5 ou heuristique) si indisponible.

## 7. API (FastAPI — réutilise `app/`)

- `GET /api/markets?round_id=` — marchés ouverts + prix courants.
- `GET /api/markets/{id}` — détail (outcomes, prix, volume).
- `POST /api/bet` — `{account, market_id, outcome, shares}` → exécute au prix LMSR, débite le compte.
- `GET /api/accounts/{id}` — solde + positions + P&L.
- `GET /api/leaderboard` — classement (P&L, Brier).
- `POST /api/rounds/{id}/resolve` (interne) — settlement après le Juge.

## 8. Stockage (simple d'abord)

**SQLite** (fichier local) au début ; migration PostgreSQL plus tard (déjà dans la stack). Tables :

- `accounts(id, name, kind, balance)`
- `markets(id, round_id, type, question, status, b, resolved_outcome, created_at)`
- `outcomes(id, market_id, label, q)`
- `positions(account_id, outcome_id, shares)`
- `trades(id, account_id, market_id, outcome_id, shares, cost, price, ts)`

## 9. UI (onglet « Marché » Streamlit)

Marchés ouverts (question + prix YES/NO en %), champ de mise, solde, portefeuille, **leaderboard** (P&L + Brier), historique. Rafraîchi à chaque round.

## 10. Structure du module & tests

```
market/
  __init__.py
  models.py        # Market, Outcome, Position, Trade, Account (Pydantic)
  lmsr.py          # cost(), price(), cost_to_trade(), max_loss()  (fonctions pures)
  engine.py        # MarketEngine : open_market, quote, place_bet
  resolution.py    # mappers RoundSummary->outcome + settle()
  scoring.py       # pnl(), brier(), leaderboard()
  forecaster.py    # LLMForecaster (+ repli déterministe)
  store.py         # persistance SQLite (interface MarketStore)
tests/
  test_lmsr.py                 # prix somment a 1 ; cout monotone ; perte bornee = b*ln(N)
  test_engine.py               # un pari debite le bon cout ; les prix bougent
  test_resolution.py           # mappers action/trajectoire/conseil ; settle paie 1/0
  test_scoring.py              # Brier correct sur cas connus
  test_integration_market.py   # open -> bets -> resolve(RoundSummary) -> settle -> leaderboard
```

Tests **offline** (sans LLM) : `RoundSummary` fabriqué + forecaster déterministe.

## 11. Découpage Cowork ↔ Claude Code

| Étape | Où |
|---|---|
| Spéc + formules LMSR + mappers de résolution + schéma tables (ce doc) | **[CW] Cowork** ✅ |
| Implémentation `market/` + tests + API + UI + SQLite | **[CC] Claude Code** |
| Forecaster LLM + budget VRAM (séquentiel) | **[CC] Claude Code** (GPU) |
| Éval calibration (Brier) sur N parties | **[CC] Claude Code** |

## 12. Plan d'implémentation (ordre conseillé)

1. **`lmsr.py` + `test_lmsr.py`** — le cœur mathématique, pur, testable sans rien (invariants : prix somment à 1, coût monotone, perte bornée).
2. **`models.py` + `store.py` (SQLite) + `engine.py`** (open / quote / bet) + tests.
3. **`resolution.py`** (mappers + settle) + `test_resolution.py` (avec un `RoundSummary` fabriqué).
4. **`scoring.py`** (P&L, Brier) + leaderboard.
5. **API FastAPI** + **onglet UI** Streamlit.
6. **`forecaster.py`** (LLM séquentiel) + éval calibration.

> Discipline : une brique à la fois, la plus simple qui marche, testée, avant la suivante.

## Références

[1] Hanson, R. — Logarithmic Market Scoring Rules (LMSR), market maker à perte bornée. <https://mason.gmu.edu/~rhanson/mktscore.pdf>

[2] Brier score (proper scoring rule) — mesure de calibration des probabilités. <https://en.wikipedia.org/wiki/Brier_score>

[3] LLMs as Strategic Actors (2026) — calibration/cadrage du comportement (motive la couche recherche). arXiv:2603.02128. <https://arxiv.org/abs/2603.02128>
