"""
Carga dos CSVs gerados por collect_nba_data.py para o Supabase.

Usa a SERVICE_ROLE key (nunca a anon key aqui) porque faz upsert —
essa key nunca deve ir para o HTML/front-end.

Configuração (.env na mesma pasta):
    SUPABASE_URL=https://xxxxx.supabase.co
    SUPABASE_SERVICE_ROLE_KEY=xxxxx

Requisitos:
    pip install supabase python-dotenv pandas

Ordem de carga importa: dim_teams e dim_players antes de
fact_player_stats, por causa das foreign keys.
"""

import math
import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
DATA_DIR = "./data"
BATCH_SIZE = 500

client = create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_value(v):
    """NaN/Infinity não são JSON válido - vira None (null no Postgres)."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def upsert_table(csv_path: str, table_name: str, conflict_cols: str):
    df = pd.read_csv(csv_path).astype(object)
    df = df.where(pd.notnull(df), None)  # 1ª passada: NaN -> None
    records = df.to_dict(orient="records")
    records = [{k: clean_value(v) for k, v in r.items()} for r in records]  # 2ª passada de segurança

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        client.table(table_name).upsert(batch, on_conflict=conflict_cols).execute()

    print(f"{table_name}: {len(records)} linhas carregadas")


def main():
    upsert_table(f"{DATA_DIR}/dim_teams.csv", "dim_teams", "team_id")
    upsert_table(f"{DATA_DIR}/dim_players.csv", "dim_players", "player_id")
    upsert_table(
        f"{DATA_DIR}/fact_player_stats.csv",
        "fact_player_stats",
        "player_id,team_id,season",
    )


if __name__ == "__main__":
    main()
