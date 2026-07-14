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
  role        text not null default 'council'       -- G8/G12 : architect|council|player|spectator
              check (role in ('architect', 'council', 'player', 'spectator')),
  -- G11 : propriété + réglages transversaux (verrouillés à la création).
  owner_id    uuid references auth.users(id) on delete set null,  -- joueur propriétaire
  ranked      boolean not null default false,       -- classée (§3) : compte pour les LP
  difficulty  text not null default 'intermediate'  -- §4 : beginner | intermediate | expert
              check (difficulty in ('beginner', 'intermediate', 'expert')),
  drift_enabled boolean not null default true,       -- la Dérive peut frapper une SI (transversal)
  result_json jsonb,                                 -- G11-c : bilan de fin de partie (§1 S6)
  language    text not null default 'fr'             -- G14 §1 : langue des dialogues (fr | en)
              check (language in ('fr', 'en'))
);
-- Migration des bases existantes (idempotent) :
alter table games add column if not exists owner_id uuid references auth.users(id) on delete set null;
alter table games add column if not exists ranked boolean not null default false;
alter table games add column if not exists difficulty text not null default 'intermediate';
alter table games add column if not exists drift_enabled boolean not null default true;
alter table games add column if not exists result_json jsonb;
alter table games add column if not exists language text not null default 'fr';
create index if not exists games_owner_idx on games (owner_id);

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
  history_json        jsonb not null default '{}',  -- G9 §4 : séries d'indices (IndexHistory)
  storyline           text not null default '',     -- G9 §5 : l'intrigue centrale (round 1)
  updated_at          timestamptz not null default now()
);
-- Migration des bases existantes (idempotent) :
alter table game_sessions add column if not exists history_json jsonb not null default '{}';
alter table game_sessions add column if not exists storyline text not null default '';

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

-- ============================== joueurs (G11) ===============================
-- Le compte de ligue : une fiche par utilisateur auth. Le pseudo est ce que tout
-- le monde voit ; l'email dérivé (`<pseudo>@wosi.local`) ne sort jamais de l'UI.
create table if not exists players (
  id         uuid primary key references auth.users(id) on delete cascade,
  pseudo     text not null unique,
  is_admin   boolean not null default false,
  lp         integer not null default 0,          -- points de ligue (§2, plancher 0)
  xp         integer not null default 0,          -- G12 §2 : carrière (ne baisse jamais)
  market_balance double precision not null default 0,  -- G12 §1 : solde de marché (carrière)
  created_at timestamptz not null default now()
);
-- Migration des bases existantes (idempotent) :
alter table players add column if not exists xp integer not null default 0;
alter table players add column if not exists market_balance double precision not null default 0;

-- G12 §2 : chaque gain d'XP daté (carrière). Écrit par le service_role ; le joueur lit le sien.
create table if not exists xp_history (
  id        text primary key,
  player_id uuid not null references players(id) on delete cascade,
  game_id   text references games(id) on delete set null,
  delta     integer not null,
  reason    text not null default '',
  ts        timestamptz not null default now()
);
create index if not exists xp_history_player_idx on xp_history (player_id, ts);

-- G12-b §5 : crises créées depuis l'UI admin (JSON validé par le schéma Pydantic Crisis,
-- JAMAIS d'écriture de fichier). Jouables par tous ; éditables/supprimables par leur auteur.
create table if not exists custom_crises (
  id         text primary key,
  owner_id   uuid not null references auth.users(id) on delete cascade,
  crisis_json jsonb not null,
  created_at timestamptz not null default now()
);

-- « admin » sans récursion RLS : SECURITY DEFINER lit players en contournant sa propre
-- politique (sinon la policy admin de players s'auto-référencerait à l'infini).
create or replace function public.is_admin() returns boolean
  language sql stable security definer set search_path = public as
$$ select coalesce((select p.is_admin from players p where p.id = auth.uid()), false) $$;

-- G11-c : chaque mouvement de LP (gain, perte, forfait), daté. Écrit par le service_role
-- (le backend crédite les LP en fin de partie) ; le joueur lit son historique.
create table if not exists lp_history (
  id        text primary key,
  player_id uuid not null references players(id) on delete cascade,
  game_id   text references games(id) on delete set null,
  delta     integer not null,
  ts        timestamptz not null default now()
);
create index if not exists lp_history_player_idx on lp_history (player_id, ts);

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

alter table players         enable row level security;  -- G11 : chacun sa fiche, admin tout
alter table lp_history      enable row level security;  -- G11-c : chacun son historique LP
alter table xp_history      enable row level security;  -- G12 : chacun son historique XP
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

-- ============================== accès G11 (comptes de ligue) ================
-- Les policies SELECT multiples s'additionnent (OR) : la « lecture publique » ci-dessus
-- (parties publiées, anon) COEXISTE avec l'accès propriétaire/admin ci-dessous.

-- players : chacun lit et gère SA fiche ; l'admin lit tout (via is_admin()).
create policy "fiche : lecture de soi"   on players for select using (auth.uid() = id or public.is_admin());
create policy "fiche : création de soi"  on players for insert with check (auth.uid() = id);
create policy "fiche : mise à jour de soi" on players for update using (auth.uid() = id) with check (auth.uid() = id);

-- lp_history / xp_history : chacun lit le sien (admin tout) ; écriture réservée au service_role.
create policy "LP : lecture de soi" on lp_history for select
  using (player_id = auth.uid() or public.is_admin());
create policy "XP : lecture de soi" on xp_history for select
  using (player_id = auth.uid() or public.is_admin());

-- custom_crises : jouables par tous (contenu de campagne), gérées par leur auteur.
alter table custom_crises enable row level security;
create policy "crise maison : lecture publique" on custom_crises for select using (true);
create policy "crise maison : gestion de soi" on custom_crises for all
  using (owner_id = auth.uid()) with check (owner_id = auth.uid());

-- INVARIANT DE SÉCURITÉ : is_admin et lp ne s'écrivent JAMAIS côté client — sinon un
-- utilisateur se promeut admin (→ lit toutes les parties) et truque le leaderboard.
-- La RLS seule ne borne pas les colonnes ; Postgres ne soustrait pas une colonne d'un
-- privilège de table → on révoque insert/update de table puis on regrante les seules
-- colonnes autorisées. is_admin/lp restent écrits par le backend service_role (qui
-- contourne la RLS) : LP crédités après une partie, admin posé en base (§2).
revoke insert, update on players from anon, authenticated;
grant insert (id, pseudo) on players to authenticated;
grant update (pseudo)     on players to authenticated;

-- games/rounds/transcripts : le propriétaire lit SES parties (même non publiées),
-- l'admin lit tout (l'ex-observatoire). Le public garde les seules parties publiées.
create policy "partie : propriétaire et admin" on games for select
  using (owner_id = auth.uid() or public.is_admin());
create policy "rounds : propriétaire et admin" on rounds for select
  using (exists (
    select 1 from games g where g.id = rounds.game_id
    and (g.owner_id = auth.uid() or public.is_admin())
  ));
create policy "transcripts : propriétaire et admin" on transcripts for select
  using (exists (
    select 1 from rounds r join games g on g.id = r.game_id
    where r.id = transcripts.round_id and (g.owner_id = auth.uid() or public.is_admin())
  ));

-- Leaderboard public : pseudo + LP seulement (jamais l'historique d'autrui). La vue
-- (propriété du créateur, hors security_invoker) contourne la RLS de players → expose
-- toutes les lignes, mais UNIQUEMENT ces deux colonnes.
create or replace view leaderboard as
  select pseudo, lp from players order by lp desc, pseudo asc;
grant select on leaderboard to anon, authenticated;
