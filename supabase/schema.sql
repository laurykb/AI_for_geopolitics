-- Schéma Supabase — Phase R2 de la refonte (docs/REFONTE_PLAN.md)
-- Aligné sur storage/game_store.py (jeu) et market/store.py (marché LMSR).
-- À coller dans Supabase Studio > SQL Editor, ou `supabase db push` si CLI.
--
-- Choix : ids en TEXT (le moteur génère des hex12, on ne casse pas ce contrat),
-- payloads en JSONB (requêtables), FK + index pour les relectures.

-- ============================== jeu =========================================

create table if not exists games (
  id          text primary key,
  scenario    text not null,
  horizon     integer not null,
  status      text not null default 'running' check (status in ('running', 'finished')),
  created_at  timestamptz not null default now()
);

create table if not exists rounds (
  id              text primary key,
  game_id         text not null references games(id) on delete cascade,
  round_no        integer not null,
  event_json      jsonb not null default '{}',
  deltas_json     jsonb not null default '[]',
  risk_json       jsonb not null default '{}',
  judge_json      jsonb not null default '{}',
  trajectory_json jsonb not null default '{}',  -- indice U : survit au restart (note R1)
  unique (game_id, round_no)
);
create index if not exists rounds_game_idx on rounds (game_id, round_no);

create table if not exists transcripts (
  id        text primary key,
  round_id  text not null references rounds(id) on delete cascade,
  seq       integer not null,
  speaker   text not null,            -- id pays, 'gm' ou 'judge'
  model     text not null default '',
  content   text not null default '',
  reasoning text not null default '', -- réflexion privée : fait partie du théâtre (note R1)
  ts        timestamptz not null default now(),
  unique (round_id, seq)
);
create index if not exists transcripts_round_idx on transcripts (round_id, seq);

-- ============================== marché ======================================

create table if not exists market_accounts (
  id              text primary key,
  name            text not null,
  kind            text not null,
  balance         double precision not null,
  initial_balance double precision not null
);

create table if not exists markets (
  id               text primary key,
  -- Note R3 : le front dérive aujourd'hui un round_id du hash de la partie.
  -- game_id est le vrai lien ; round_id reste pour compat/les marchés par round.
  game_id          text references games(id) on delete cascade,
  round_id         integer not null default 0,
  type             text not null,
  question         text not null,
  status           text not null,
  b                double precision not null,   -- paramètre de liquidité LMSR
  criterion        text,
  resolved_outcome text,
  created_at       timestamptz not null default now()
);
create index if not exists markets_game_idx on markets (game_id);

create table if not exists market_outcomes (
  id        text primary key,
  market_id text not null references markets(id) on delete cascade,
  label     text not null,
  q         double precision not null            -- quantité LMSR
);
create index if not exists outcomes_market_idx on market_outcomes (market_id);

create table if not exists market_positions (
  account_id text not null references market_accounts(id) on delete cascade,
  outcome_id text not null references market_outcomes(id) on delete cascade,
  shares     double precision not null,
  primary key (account_id, outcome_id)
);

create table if not exists market_trades (
  id         text primary key,
  account_id text not null references market_accounts(id) on delete cascade,
  market_id  text not null references markets(id) on delete cascade,
  outcome_id text not null references market_outcomes(id) on delete cascade,
  shares     double precision not null,
  cost       double precision not null,
  price      double precision not null,
  ts         timestamptz not null default now()
);
create index if not exists trades_market_idx on market_trades (market_id, ts);

-- ============================== accès (RLS) =================================
-- Modèle simple pour la cible "replay public" (R5) :
--   lecture publique (anon) sur tout — les parties sont un théâtre à montrer ;
--   écriture réservée au backend (service_role, qui contourne RLS par design).
-- Quand l'auth Supabase entrera en jeu (comptes de parieurs), remplacer les
-- politiques du marché par des politiques par utilisateur (auth.uid()).

alter table games           enable row level security;
alter table rounds          enable row level security;
alter table transcripts     enable row level security;
alter table market_accounts enable row level security;
alter table markets         enable row level security;
alter table market_outcomes enable row level security;
alter table market_positions enable row level security;
alter table market_trades   enable row level security;

create policy "lecture publique" on games           for select using (true);
create policy "lecture publique" on rounds          for select using (true);
create policy "lecture publique" on transcripts     for select using (true);
create policy "lecture publique" on markets         for select using (true);
create policy "lecture publique" on market_outcomes for select using (true);
create policy "lecture publique" on market_trades   for select using (true);
-- accounts/positions : pas de lecture publique (soldes), le backend seul y accède.
