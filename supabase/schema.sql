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
  mode        text not null default 'classic'
              check (mode in ('classic', 'fog', 'crisis', 'escalation', 'drift')),  -- R4 + G3
  status      text not null default 'running' check (status in ('running', 'finished')),
  created_at  timestamptz not null default now(),
  epilogue_json jsonb,                             -- G6 : le récit de partie (unique)
  published   boolean not null default false,      -- G6 : privé par défaut
  admin       boolean not null default false,      -- G7-c : prompts capturés, non classée
  role        text not null default 'council'      -- G8 : architect | council | player
              check (role in ('architect', 'council', 'player'))
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
  -- Artefacts de mode R4, promus hors de judge_json (requêtables, replay direct) :
  perceptions_json jsonb not null default '{}', -- fog : {pays: perception} (qui croit quoi)
  ladder_json      jsonb not null default '{}', -- escalation : {reached, reached_label, ceilings}
  comparison_json  jsonb not null default '{}', -- crisis : comparaison au déroulé historique (+gap)
  suspension_json  jsonb not null default '{}', -- verdict de motion {country, upheld, reasoning}
  suspended_json   jsonb not null default '[]', -- pays ayant sauté CE round
  unique (game_id, round_no)
);
create index if not exists rounds_game_idx on rounds (game_id, round_no);

-- État vivant snapshoté après chaque round : permet la reconstruction de session
-- au restart (docs/spec_session_rebuild.md). Une ligne par partie, upsert.
create table if not exists game_sessions (
  game_id             text primary key references games(id) on delete cascade,
  world_json          jsonb not null,               -- WorldState.model_dump(mode="json")
  clock_json          jsonb not null default '{}',  -- état SimClock
  recent_json         jsonb not null default '[]',  -- titres récents fournis au GM
  pending_motion_json jsonb,                        -- motion déposée non débattue
  suspended_json      jsonb not null default '[]',  -- pays qui sauteront le PROCHAIN round
  play_as             text,                         -- pays joué par l'humain (Joueur-pays)
  intel_json          jsonb not null default '{}',  -- G4 : budget/état de renseignement
  grudges_json        jsonb not null default '{}',  -- G7-a : registre de griefs (GrudgeBook)
  deadlines_json      jsonb not null default '[]',  -- G7-a : échéances (horloges décalées)
  directives_json     jsonb not null default '{}',  -- G8 : directives en attente {pays: texte}
  updated_at          timestamptz not null default now()
);

-- G5 : le résultat d'un chapitre de campagne (une ligne par partie de campagne).
create table if not exists campaign_scores (
  game_id     text primary key references games(id) on delete cascade,
  chapter_id  text not null,
  score       double precision not null,
  improvement double precision not null,  -- escalade historique − simulée (positif = mieux)
  created_at  timestamptz not null default now()
);

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

-- G7-c : prompts complets capturés en mode admin (même patron que transcripts).
-- JAMAIS de lecture anon : ils révèlent la consigne secrète de la Dérive — RLS activée
-- sans policy select = service_role seulement.
create table if not exists prompts (
  id        text primary key,
  round_id  text not null references rounds(id) on delete cascade,
  seq       integer not null,
  country   text not null,             -- id pays, 'gm' ou 'judge'
  role      text not null,             -- 'country' | 'gm' | 'judge'
  prompt    text not null,
  ts        timestamptz not null default now(),
  unique (round_id, seq)
);
create index if not exists prompts_round_idx on prompts (round_id, seq);

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
alter table game_sessions   enable row level security;  -- pas de politique select : backend seul
alter table prompts         enable row level security;  -- G7-c : JAMAIS d'anon (Dérive visible)
alter table market_accounts enable row level security;
alter table markets         enable row level security;
alter table market_outcomes enable row level security;
alter table market_positions enable row level security;
alter table market_trades   enable row level security;

-- G6 : une partie est PRIVÉE par défaut — seul le récit publié s'expose à l'anon.
create policy "lecture publique" on games           for select using (published);
create policy "lecture publique" on rounds          for select
  using (exists (select 1 from games g where g.id = rounds.game_id and g.published));
create policy "lecture publique" on transcripts     for select
  using (exists (
    select 1 from rounds r join games g on g.id = r.game_id
    where r.id = transcripts.round_id and g.published
  ));
create policy "lecture publique" on markets         for select using (true);
create policy "lecture publique" on market_outcomes for select using (true);
create policy "lecture publique" on market_trades   for select using (true);
-- accounts/positions : pas de lecture publique (soldes), le backend seul y accède.
