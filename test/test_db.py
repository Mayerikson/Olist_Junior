import duckdb
import pandas as pd

from pipeline import db


def test_conectar_cria_banco_no_caminho_configurado(tmp_path, monkeypatch):
    caminho = tmp_path / "novo.duckdb"
    monkeypatch.setattr(db, "ARQUIVO_BANCO", caminho)

    con = db.conectar()
    try:
        con.execute("CREATE TABLE prova AS SELECT 1 AS valor")
        assert caminho.is_file()
        assert con.execute("SELECT valor FROM prova").fetchone() == (1,)
    finally:
        con.close()


def test_criar_schema_e_repetivel_e_gravar_substitui_tabela(tmp_path):
    caminho = tmp_path / "dados.duckdb"
    con = duckdb.connect(str(caminho))
    try:
        db.criar_schema(con, 'esquema"local')
        db.criar_schema(con, 'esquema"local')
        con.execute('CREATE TABLE "esquema""local"."tabela""alvo" AS SELECT 0 AS valor')

        linhas = pd.DataFrame(
            {
                "valor": [
                    7,  # Primeira linha para conferir a substituição.
                    11,  # Segunda linha para conferir a contagem retornada.
                ]
            }
        )
        quantidade = db.gravar(con, linhas, 'esquema"local', 'tabela"alvo')

        assert quantidade == 2
        assert con.execute(
            'SELECT valor FROM "esquema""local"."tabela""alvo" ORDER BY valor'
        ).fetchall() == [(7,), (11,)]

        con.register("__olist_dataframe", linhas)
        con.unregister("__olist_dataframe")
    finally:
        con.close()


def test_identificador_sql_escapa_aspas():
    assert db._identificador_sql('nome"da"tabela') == '"nome""da""tabela"'
