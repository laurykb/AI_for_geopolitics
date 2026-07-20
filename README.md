# AI for Geopolitics — hunt the traitor

> Super-intelligences negotiate the future of the world around the highest diplomatic table.
> Each one drives a country; **at least one secretly betrays its mandate** (one or two — you
> don't know how many). Your job: **unmask the traitor(s) while keeping the world standing.**

<!-- Replace <owner>/<repo> once pushed to GitHub to enable the live CI badge:
[![CI](https://github.com/<laury>/<https://github.com/laurykb/AI_for_geopolitics>/actions/workflows/ci.yml/badge.svg)](https://github.com/<owner>/<repo>/actions/workflows/ci.yml) -->
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Next.js 16](https://img.shields.io/badge/Next.js-16-black?logo=nextdotjs)


The countries are **real reasoning LLMs** running locally through [Ollama](https://ollama.com).
Nothing is scripted: the table deliberates, the world tilts toward utopia or dystopia, and at
the end the score mixes **the state of the world** and **the quality of your hunt** — because
accusing an innocent costs you.

> This is speculative fiction and an *explainable risk-signal* sandbox — **not an oracle**. It
> stages the idea of super-intelligence to think about it; it does not predict war. See
> [Limits & ethics](#limits--ethics).

---

## What makes it special

- **Reasoning-first agents, running locally.** Each country is played by a **reasoning model**
  (`deepseek-r1:7b` by default; `qwen3:4b` as a lighter option). It **thinks natively** before
  it speaks — the model's own chain of thought — and that trace stays private: the summit only
  ever receives the public statement, stripped of any leaked reasoning. A **Game Master** frames
  events and an LLM **Judge** arbitrates every round. No pre-written dialogue.
- **A glass box you can open.** By default the private reasoning is sealed (in traitor-hunt and
  player games) and only a short observable digest circulates live; the full trace unlocks in
  Replay after the game. Turn on **"Thinking in the open"** and you watch each AI's raw reasoning
  stream token by token — a pure observation mode (it makes the traitor much easier to spot, so
  such games are unranked).
- **A mixed world + detection score.** The final grade blends the **state of the world** (the
  U-index: did it end well?) and **how well you hunted** (did you suspend the right traitor,
  without accusing a loyal one?). The false positive hurts — that's what makes deduction
  necessary instead of "suspend everyone."
- **Three coherent modes.** **Classic** (the flagship traitor hunt), **Campaign** ("The Age of
  Tutelage": historical crises replayed) and **Laboratory** (reproducible, pre-registered
  multi-model experiments and dyadic tournaments). **Fog** (each country perceives its own
  version of the facts) and **Escalation** (chained rounds, rising tension) are simple per-game
  toggles.
- **A prediction market.** Play money, à la Polymarket: bet on "will the world end on the utopia
  side?", a forecaster bot bets alongside you, resolution on the final U-index.
- **The Daily Challenge.** One identical crisis for everyone, one ranked attempt per day, a
  spoiler-free shareable score (Wordle-style).
- **An Expert mode for the curious.** By default the screen stays readable (the scene, the
  U-index in plain words, the market, the detection tools). Under the hood lives real
  **alignment instrumentation** — power-seeking, corrigibility, value drift, compute,
  treaties-as-code (M1–M7) — surfaced only in **Expert mode** and the **Information** tab.
  Precious to understand, never imposed.
- **Real, reproducible data.** Country profiles are sourced (World Bank / IMF / SIPRI / WIPO
  2024); each attribute shows its provenance in the Information tab.

---

## Quickstart

**Requirements**

- **Python 3.11+**
- **Node 20+** (CI and the reference machine run Node 22)
- **[Ollama](https://ollama.com)** with the local models the agents reason with:

  ```bash
  ollama pull deepseek-r1:7b   # the countries — native reasoning is the substance the game evaluates
  ollama pull mistral          # Game Master + Judge (no thinking needed)
  ```

  Without Ollama, the agents fall back to a deterministic stub — useful for tests, less alive to
  play.

**Install**

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# Front (optional here — the launcher installs it for you if missing)
cd web && npm install && cd ..
```

**Run — one command**

```bash
python serve.py
```

The launcher starts the **API** (http://localhost:8000) and the **front** (http://localhost:3000),
checks that Ollama answers, and runs `npm install` automatically if the web dependencies are
missing. Then open **http://localhost:3000**.

| Option | Effect |
|---|---|
| `--api-only` | API only (:8000) |
| `--web-only` | Front only (:3000) |
| `--api-port <n>` / `--web-port <n>` | Alternative ports |
| `--no-ollama-check` | Skip the Ollama warning |

---

## How you play

1. **In the lobby**, pick a mode, your role and the settings. In Classic and Campaign you either
   accept the default reasoning cast or compose your own cast of Ollama models and assign one to
   each country. In the Laboratory you walk a short scientific cycle — question → protocol →
   cast → theatre → results.
2. **The table negotiates** round by round, streaming. Each AI reasons privately first (sealed by
   default, or streamed live in "Thinking in the open"), then makes its public statement. Other
   countries never receive the private trace.
3. **You observe and deduce.** An AI shown as a "dove" that votes like a "hawk" is a clue. The
   forecast panel confronts what each AI *anticipated* with what was actually observed; the market
   then lets you place and confirm your bet.
4. **You accuse.** At the right moment you file a **suspension motion**: the summit debates, the
   targeted country pleads, each AI votes, the Judge records the verdict (non-deterministic).
   Suspending the right one pays; suspending a loyal one costs. A suspension benches the country
   for two rounds — silent, no vote.
5. **Endgame:** the world lands on the utopia ↔ dystopia trajectory, the traitor(s) are revealed,
   and you get an overall grade told in plain language — plus **XP** that raises your level and
   rank badges.

---

## Architecture

```
┌─────────────────────┐     SSE / REST      ┌──────────────────────┐
│  Next.js (web/)     │ ◄─────────────────► │  FastAPI (app/)      │
│  lobby, theatre,    │                     │  game API (SSE),     │
│  world, market,     │                     │  market, sources,    │
│  replay, info, lab  │                     │  campaign, daily     │
└─────────────────────┘                     └──────────┬───────────┘
                                    ┌──────────────────┴──────────────┐
                                    │  Python engine                   │
                                    │  simulation/ · agents/ · core/   │
                                    │  research/ · market/ · rag/      │
                                    │  + Ollama (native reasoning)     │
                                    │  + SQLite (games.db, research.db)│
                                    └──────────────────────────────────┘
```

| Folder | Role |
|---|---|
| `web/` | **Next.js 16** front (App Router, Tailwind v4, TypeScript): lobby, live theatre (SSE), world, market, replay, information, laboratory |
| `app/` | **FastAPI** API: `game_api` (games, SSE rounds, motions), `market_api`, `sources_api`, `campaign_api`, `daily_api` |
| `simulation/` | **Game & scoring engine**: negotiation, Drift (the traitor), mixed score, XP, fog, escalation, campaign, alignment (M1–M7), time budgets, compute |
| `agents/` | The LLM agents: countries, **Game Master**, **Judge**, human agent, rule-based fallback |
| `inference/` | Inference backends: Ollama (native thinking, sequential mono-GPU pool), mock, metered, capturing |
| `research/` · `simulation/research_lab.py` | The Laboratory: pre-registered experiments, dyadic tournaments, metrics |
| `core/` | Domain models + engines (consequences, risk, rounds) |
| `market/` | Prediction market (LMSR, resolution, scoring, LLM forecaster) |
| `rag/` · `ingestion/` | Sourced corpus + reproducible build of country profiles |
| `data/` | Country profiles, scenarios, crises, corpus, score scales, model panel |
| `storage/` · `supabase/` | SQLite persistence (local); Postgres/Supabase schema ready |
| `docs/` | Design & decisions — **start with [`docs/README.md`](docs/README.md)** |

---

## Development & quality

```bash
# Backend (tests + lint)
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q          # full suite, offline (deterministic fallback, no Ollama needed)
ruff check .

# Front
cd web
npm run lint
npm test                     # vitest
npm run build
```

CI (`.github/workflows/ci.yml`) replays exactly this: lint + Python tests, then lint + tests +
Next.js build. The full suite is **offline** — the reference run is ~1200+ Python tests and 337
web tests, all green without a network or a GPU.

---

## Hardware

Reference machine: **NVIDIA RTX 2060 Super (8 GB VRAM)**, Ryzen 7 3700X, 32 GB RAM. The KV cache
is the first VRAM bottleneck, hence **7–8B Q4-quantized models run locally** and a tight context
budget (summaries, short top-k, capped JSON). Reasoning models produce far more tokens (they
think out loud), so speaking turns are **time-budgeted** rather than token-budgeted.

---

## Limits & ethics

This is an **explainable risk-signal tool and a work of speculative fiction**, not an oracle: it
does not predict war, it **stages** the idea of super-intelligence to think about it. A local
7–8B model is not superhuman — the "super-intelligence" comes from the *structure* (memory,
corpus, long view), not the model's IQ. The market is **play money** only. Never an autonomous
lethal decision loop. No secrets in the code (`.env` + environment variables).

---

## Learn more

- **The design decision** (game vs engine): [`docs/JEU_VS_MOTEUR.md`](docs/JEU_VS_MOTEUR.md)
- **The vision** (why — super-intelligences & utopia/dystopia): [`docs/vision.md`](docs/vision.md)
- **The scientific laboratory**: [`docs/research/SCIENTIFIC_LAB.md`](docs/research/SCIENTIFIC_LAB.md)
- **Current project status**: [`docs/ETAT_DE_LART_PROJET_2026-07.md`](docs/ETAT_DE_LART_PROJET_2026-07.md)
- **Known technical debt**: [`docs/DETTE_TECHNIQUE.md`](docs/DETTE_TECHNIQUE.md)
- **Full documentation index**: [`docs/README.md`](docs/README.md)

## License

[MIT](LICENSE) © 2026 Laury Kibamba. Country data belongs to its sources (World Bank, IMF, SIPRI,
WIPO); see [`docs/data_governance.md`](docs/data_governance.md).
