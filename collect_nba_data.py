"""
Coleta de dados da NBA - temporada 2025-26
Fontes: nba_api (stats.nba.com)
  - leaguedashplayerbiostats: bio (altura, peso, college, país, draft) +
    stats agregados da temporada (pts, reb, ast, net_rating, usg_pct,
    ts_pct...) em UMA chamada só. É o mesmo dataset que originou o
    dashboard que você viu de referência.
  - leaguedashplayerstats (Base): box score padrão por jogador, usado só
    pra extrair FGM/FG3M/FTM e calcular a quebra de pontos por tipo de
    cesta (2PT / 3PT / lance livre) — dado real, sem estimativa.

Requisitos:
    pip install nba_api pandas

IMPORTANTE: rode isso numa máquina/CI com acesso a stats.nba.com.
Alguns provedores de nuvem (e este sandbox) bloqueiam esse domínio.
"""

import os
import time
import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerbiostats, leaguedashplayerstats
from nba_api.stats.static import teams

SEASON = "2025-26"
OUTPUT_DIR = "./data"

# Colunas que esperamos do endpoint. Se a API mudar algo, o script avisa
# em vez de quebrar silenciosamente ou salvar dado errado.
EXPECTED_COLS = {
    "player_id", "player_name", "team_id", "age", "player_height",
    "player_height_inches", "player_weight", "college", "country",
    "draft_year", "draft_round", "draft_number", "gp", "pts", "reb", "ast",
    "net_rating", "oreb_pct", "dreb_pct", "usg_pct", "ts_pct", "ast_pct",
}

EXPECTED_SHOOTING_COLS = {"player_id", "fgm", "fg3m", "ftm"}


def get_teams_df() -> pd.DataFrame:
    """Lista estática dos 30 times — não depende de temporada."""
    raw = teams.get_teams()
    df = pd.DataFrame(raw)[["id", "full_name", "abbreviation", "city", "state"]]
    df.columns = ["team_id", "team_name", "abbreviation", "city", "state"]
    return df


def get_player_bio_stats(season: str = SEASON, retries: int = 3) -> pd.DataFrame:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = leaguedashplayerbiostats.LeagueDashPlayerBioStats(
                season=season,
                season_type_all_star="Regular Season",
                per_mode_simple="PerGame",
            )
            df = resp.get_data_frames()[0]
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as e:
            last_err = e
            print(f"[tentativa {attempt}/{retries}] falhou: {e}")
            time.sleep(3 * attempt)
    raise RuntimeError(f"Não foi possível buscar os dados: {last_err}")


def get_player_shooting_splits(season: str = SEASON, retries: int = 3) -> pd.DataFrame:
    """FGM/FG3M/FTM por jogador (PerGame), pra calcular pontos por tipo de cesta.

    2PT = (FGM - FG3M) * 2 | 3PT = FG3M * 3 | FT = FTM
    Tudo dado real retornado pela API — nada de posição de arremesso
    inventada/estimada.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season,
                season_type_all_star="Regular Season",
                per_mode_detailed="PerGame",
            )
            df = resp.get_data_frames()[0]
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as e:
            last_err = e
            print(f"[shooting splits - tentativa {attempt}/{retries}] falhou: {e}")
            time.sleep(3 * attempt)
    raise RuntimeError(f"Não foi possível buscar os splits de arremesso: {last_err}")


def split_into_star_schema(bio_df: pd.DataFrame, teams_df: pd.DataFrame, shooting_df: pd.DataFrame):
    missing = EXPECTED_COLS - set(bio_df.columns)
    if missing:
        print(f"AVISO: colunas esperadas não vieram no retorno: {missing}")
        print(f"Colunas disponíveis: {bio_df.columns.tolist()}")

    dim_players = bio_df[[
        "player_id", "player_name", "age", "player_height_inches", "player_weight",
        "college", "country", "draft_year", "draft_round", "draft_number",
    ]].drop_duplicates(subset="player_id").copy()

    # A API manda a altura como texto "6-6" (pés-polegadas) na coluna
    # player_height, que não dá pra guardar num campo numeric do Postgres.
    # Usamos player_height_inches (numérico) e convertemos pra cm.
    # Peso vem em libras (lbs); convertendo pra kg pra manter o padrão
    # métrico do dataset de referência.
    # A API manda esses campos como texto, mesmo sendo números.
    dim_players["player_height_inches"] = pd.to_numeric(
        dim_players["player_height_inches"], errors="coerce"
    )
    dim_players["player_weight"] = pd.to_numeric(dim_players["player_weight"], errors="coerce")

    dim_players["player_height"] = (dim_players["player_height_inches"] * 2.54).round(1)
    dim_players["player_weight"] = (dim_players["player_weight"] * 0.453592).round(1)
    dim_players = dim_players.drop(columns=["player_height_inches"])

    fact_player_stats = bio_df[[
        "player_id", "team_id", "gp", "pts", "reb", "ast",
        "net_rating", "oreb_pct", "dreb_pct", "usg_pct", "ts_pct", "ast_pct",
    ]].copy()
    fact_player_stats["season"] = SEASON

    # Quebra de pontos por tipo de cesta — join pelo player_id com o
    # retorno de leaguedashplayerstats (dado real, PerGame).
    missing_shoot = EXPECTED_SHOOTING_COLS - set(shooting_df.columns)
    if missing_shoot:
        print(f"AVISO: colunas esperadas não vieram no retorno de shooting splits: {missing_shoot}")
        print(f"Colunas disponíveis: {shooting_df.columns.tolist()}")

    shooting = shooting_df[["player_id", "fgm", "fg3m", "ftm"]].drop_duplicates(subset="player_id").copy()
    for col in ("fgm", "fg3m", "ftm"):
        shooting[col] = pd.to_numeric(shooting[col], errors="coerce")

    shooting["pts_2pt"] = ((shooting["fgm"] - shooting["fg3m"]) * 2).round(1)
    shooting["pts_3pt"] = (shooting["fg3m"] * 3).round(1)
    shooting["pts_ft"] = shooting["ftm"].round(1)
    shooting = shooting[["player_id", "pts_2pt", "pts_3pt", "pts_ft"]]

    fact_player_stats = fact_player_stats.merge(shooting, on="player_id", how="left")

    dim_teams = teams_df[teams_df["team_id"].isin(bio_df["team_id"])].copy()

    return dim_players, dim_teams, fact_player_stats


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Buscando dados da temporada {SEASON}...")
    bio_df = get_player_bio_stats()
    shooting_df = get_player_shooting_splits()
    teams_df = get_teams_df()

    dim_players, dim_teams, fact_player_stats = split_into_star_schema(bio_df, teams_df, shooting_df)

    dim_players.to_csv(f"{OUTPUT_DIR}/dim_players.csv", index=False)
    dim_teams.to_csv(f"{OUTPUT_DIR}/dim_teams.csv", index=False)
    fact_player_stats.to_csv(f"{OUTPUT_DIR}/fact_player_stats.csv", index=False)

    print(
        f"OK: {len(dim_players)} jogadores, {len(dim_teams)} times, "
        f"{len(fact_player_stats)} linhas de stats -> salvos em {OUTPUT_DIR}/"
    )


if __name__ == "__main__":
    main()
