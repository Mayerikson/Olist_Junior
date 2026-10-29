"""Helpers for the local Olist DuckDB database.

The raw folder and database path are anchored to the project rather than the
current working directory so the command-line scripts use the same files no
matter where they are launched from. Table creation replaces prior contents
to make reruns safe, and row counts are queried from DuckDB as the source of
truth for ingestion output.
"""

from pathlib import Path

import duckdb
import pandas as pd

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
PASTA_RAW = RAIZ_PROJETO / "raw"
ARQUIVO_BANCO = RAIZ_PROJETO / "olist.duckdb"


def _identificador_sql(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def conectar() -> duckdb.DuckDBPyConnection:
    """Open the project database, creating it when it does not exist."""
    return duckdb.connect(str(ARQUIVO_BANCO))


def criar_schema(con: duckdb.DuckDBPyConnection, nome: str) -> None:
    """Create a schema only when it does not already exist."""
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {_identificador_sql(nome)}")


def gravar(
    con: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    schema: str,
    tabela: str,
) -> int:
    """Replace a table with a DataFrame and return the database row count."""
    schema_sql = _identificador_sql(schema)
    tabela_sql = _identificador_sql(tabela)
    relacao = "__olist_dataframe"
    con.register(relacao, df)
    try:
        con.execute(
            f"CREATE OR REPLACE TABLE {schema_sql}.{tabela_sql} "
            f"AS SELECT * FROM {relacao}"
        )
        return con.execute(
            f"SELECT COUNT(*) FROM {schema_sql}.{tabela_sql}"
        ).fetchone()[0]
    finally:
        con.unregister(relacao)
