-- ============================================================
-- Schema: NBA Dashboard (temporada 2025-26)
-- Banco: Supabase (Postgres)
-- Modelo: esquema estrela simples, já pensado pra crescer —
--         quando quiser adicionar outra temporada, é só rodar
--         o load de novo com outro valor de "season", sem
--         alterar o schema.
-- ============================================================

create table if not exists dim_teams (
    team_id      bigint primary key,
    team_name    text not null,
    abbreviation text not null,
    city         text,
    state        text
);

create table if not exists dim_players (
    player_id      bigint primary key,
    player_name    text not null,
    age            numeric,
    player_height  numeric,   -- cm
    player_weight  numeric,   -- kg
    college        text,
    country        text,
    draft_year     text,
    draft_round    text,
    draft_number   text
);

create table if not exists fact_player_stats (
    player_id    bigint references dim_players(player_id),
    team_id      bigint references dim_teams(team_id),
    season       text not null,
    gp           integer,
    pts          numeric,
    reb          numeric,
    ast          numeric,
    net_rating   numeric,
    oreb_pct     numeric,
    dreb_pct     numeric,
    usg_pct      numeric,
    ts_pct       numeric,
    ast_pct      numeric,
    pts_2pt      numeric,   -- pontos/jogo vindos de cesta de 2 (FGM-FG3M)*2, endpoint leaguedashplayerstats
    pts_3pt      numeric,   -- pontos/jogo vindos de cesta de 3 (FG3M*3)
    pts_ft       numeric,   -- pontos/jogo vindos de lance livre (FTM)
    primary key (player_id, team_id, season)
);

-- ============================================================
-- View plana para o front-end.
-- Motivo: PostgREST não faz join arbitrário fácil via REST simples;
-- uma view já "achatada" evita o front ter que fazer 3 requests
-- e juntar na mão em JS.
-- ============================================================
create or replace view vw_player_stats as
select
    f.season,
    p.player_id,
    p.player_name,
    p.age,
    p.player_height,
    p.player_weight,
    p.college,
    p.country,
    p.draft_year,
    t.team_id,
    t.team_name,
    t.abbreviation as team_abbreviation,
    f.gp,
    f.pts,
    f.reb,
    f.ast,
    f.net_rating,
    f.oreb_pct,
    f.dreb_pct,
    f.usg_pct,
    f.ts_pct,
    f.ast_pct,
    f.pts_2pt,
    f.pts_3pt,
    f.pts_ft
from fact_player_stats f
join dim_players p on p.player_id = f.player_id
join dim_teams   t on t.team_id   = f.team_id;

-- ============================================================
-- Segurança: leitura pública, escrita bloqueada pro client.
-- O front-end usa a anon key (segura de expor); as cargas usam
-- a service_role key (nunca vai pro HTML).
-- ============================================================
alter table dim_teams enable row level security;
alter table dim_players enable row level security;
alter table fact_player_stats enable row level security;

create policy "public read dim_teams" on dim_teams
    for select using (true);

create policy "public read dim_players" on dim_players
    for select using (true);

create policy "public read fact_player_stats" on fact_player_stats
    for select using (true);

-- Nenhuma policy de insert/update/delete foi criada para o role "anon" —
-- ou seja, o front-end só consegue LER, mesmo que alguém pegue a anon key.
