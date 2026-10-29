"""Run DuckDB's browser UI against the existing project database.

The existing database is checked before connecting because DuckDB otherwise
creates an empty file that can be mistaken for an ingestion result. Installing
and loading the UI extension enables the requested browser interface; its
server depends on the connection staying alive, so the process waits until
Ctrl+C, stops the server explicitly, and closes the connection to release the
write lock for ingestion. Printing the URL and shutdown instruction makes
that lifetime controllable. UTF-8 stdout keeps the Portuguese text readable
in the Windows Command Prompt.
"""

import sys
import time
from pathlib import Path

import duckdb

ARQUIVO_BANCO = Path(__file__).resolve().parent / "olist.duckdb"
URL_UI = "http://localhost:4213"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if not ARQUIVO_BANCO.is_file():
        print(
            f"Banco não encontrado em {ARQUIVO_BANCO}. "
            "É preciso rodar a ingestão antes."
        )
        raise SystemExit(1)

    con = duckdb.connect(str(ARQUIVO_BANCO))
    try:
        con.execute("INSTALL ui")
        con.execute("LOAD ui")
        con.execute("CALL start_ui()")
        print(f"UI disponível em {URL_UI}")
        print("Ctrl+C para encerrar")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            con.execute("CALL stop_ui_server()")
    finally:
        con.close()


if __name__ == "__main__":
    main()
