from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from pipeline import db, marts, transformacao


def _preparar_execucao(tmp_path, monkeypatch):
    caminho = tmp_path / "teste.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    monkeypatch.setattr(db, "ARQUIVO_BANCO", caminho)
    monkeypatch.setattr(marts, "PASTA_MARTS", pasta_sql)
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA refined")
    for tabela in transformacao.TABELAS:
        con.execute(
            f'CREATE TABLE refined."{tabela}" AS SELECT 1 AS valor WHERE FALSE'
        )
    con.execute("CREATE SCHEMA marts")
    con.execute("CREATE TABLE marts.anterior AS SELECT 42 AS valor")
    con.close()
    return caminho, pasta_sql


def _ler_sql(nome):
    arquivo = Path(__file__).resolve().parents[1] / "sql" / "marts" / nome
    return arquivo.read_text(encoding="utf-8")


def test_arquivo_sem_prefixo_para_antes_de_alterar_schema(tmp_path, monkeypatch):
    caminho, pasta_sql = _preparar_execucao(tmp_path, monkeypatch)
    (pasta_sql / "sem_prefixo.sql").write_text(
        "SELECT 1 AS valor", encoding="utf-8"
    )

    with pytest.raises(SystemExit) as erro:
        marts.main()

    assert erro.value.code == 1
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute("SELECT valor FROM marts.anterior").fetchone() == (42,)
    finally:
        con.close()


def test_mart_vazio_faz_rollback_e_preserva_schema_anterior(
    tmp_path, monkeypatch
):
    caminho, pasta_sql = _preparar_execucao(tmp_path, monkeypatch)
    (pasta_sql / "01_vazio.sql").write_text(
        "SELECT 1 AS valor WHERE FALSE", encoding="utf-8"
    )

    with pytest.raises(SystemExit) as erro:
        marts.main()

    assert erro.value.code == 1
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute("SELECT valor FROM marts.anterior").fetchone() == (42,)
        assert con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'marts' AND table_name = 'vazio'"
        ).fetchone() == (0,)
    finally:
        con.close()


def test_arquivo_sql_apagado_remove_mart_na_execucao_seguinte(
    tmp_path, monkeypatch
):
    caminho, pasta_sql = _preparar_execucao(tmp_path, monkeypatch)
    primeiro = pasta_sql / "01_primeiro.sql"
    segundo = pasta_sql / "02_segundo.sql"
    primeiro.write_text("SELECT 1 AS valor", encoding="utf-8")
    segundo.write_text("SELECT 2 AS valor", encoding="utf-8")

    marts.main()
    segundo.unlink()
    marts.main()

    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute("SELECT valor FROM marts.primeiro").fetchone() == (1,)
        assert con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'marts' AND table_name = 'segundo'"
        ).fetchone() == (0,)
    finally:
        con.close()


def test_vendas_mensais_conta_pedido_uma_vez_e_exclui_cancelado(tmp_path):
    con = duckdb.connect(str(tmp_path / "vendas.duckdb"))
    try:
        con.execute("CREATE SCHEMA refined")
        con.execute(
            "CREATE TABLE refined.pedidos "
            "(pedido_id VARCHAR, data_compra TIMESTAMP, status VARCHAR)"
        )
        con.execute(
            "CREATE TABLE refined.itens_pedido "
            "(pedido_id VARCHAR, preco DECIMAL(10,2))"
        )
        # Pedido válido com dois itens; deve contar como um pedido.
        con.execute(
            "INSERT INTO refined.pedidos VALUES "
            "('valido-1', TIMESTAMP '2017-01-10 10:00:00', 'delivered')"
        )  # Pedido válido com dois itens em janeiro.
        con.execute(
            "INSERT INTO refined.itens_pedido VALUES "
            "('valido-1', 10.00), ('valido-1', 4.00)"
        )  # Dois itens provam que o pedido distinto só conta uma vez.
        # Pedido válido adicional para exercitar DISTINCT com um segundo pedido.
        con.execute(
            "INSERT INTO refined.pedidos VALUES "
            "('valido-2', TIMESTAMP '2017-01-11 10:00:00', 'delivered')"
        )  # Segundo pedido válido no mesmo mês.
        con.execute(
            "INSERT INTO refined.itens_pedido VALUES ('valido-2', 8.00)"
        )  # Receita válida incluída no total mensal.
        # Pedido cancelado de alto valor deve ficar fora da receita e dos pedidos.
        con.execute(
            "INSERT INTO refined.pedidos VALUES "
            "('cancelado', TIMESTAMP '2017-01-12 10:00:00', 'canceled')"
        )  # Cancelamento precisa ser excluído mesmo com itens associados.
        con.execute(
            "INSERT INTO refined.itens_pedido VALUES ('cancelado', 900.00)"
        )  # Valor alto confirma que cancelado não entra na receita.

        consulta = _ler_sql("01_vendas_mensais.sql")
        resultado = con.execute(consulta).fetchone()

        assert resultado == (date(2017, 1, 1), 2, Decimal("22.00"))
    finally:
        con.close()


def test_entrega_as_15h_no_dia_previsto_conta_como_no_prazo(tmp_path):
    con = duckdb.connect(str(tmp_path / "entregas.duckdb"))
    try:
        con.execute("CREATE SCHEMA refined")
        con.execute(
            "CREATE TABLE refined.pedidos "
            "(status VARCHAR, data_entrega TIMESTAMP, data_entrega_prevista DATE)"
        )
        # Entrega às 15h no dia previsto deve ser considerada pontual.
        con.execute(
            "INSERT INTO refined.pedidos VALUES "
            "('delivered', TIMESTAMP '2017-01-10 15:00:00', DATE '2017-01-10')"
        )  # Entrega às 15h no mesmo dia previsto é pontual.
        # Entrega no dia seguinte é atraso.
        con.execute(
            "INSERT INTO refined.pedidos VALUES "
            "('delivered', TIMESTAMP '2017-01-11 00:01:00', DATE '2017-01-10')"
        )  # Entrega no dia seguinte compõe o atraso.
        # Data nula não participa do denominador do mart.
        con.execute(
            "INSERT INTO refined.pedidos VALUES "
            "('delivered', NULL, DATE '2017-01-10')"
        )  # Data nula não deve entrar no denominador.
        # Pedido ainda enviado não pertence ao conjunto de entregues.
        con.execute(
            "INSERT INTO refined.pedidos VALUES "
            "('shipped', TIMESTAMP '2017-01-10 12:00:00', DATE '2017-01-10')"
        )  # Pedido não entregue não deve ser contabilizado.

        resultado = con.execute(_ler_sql("03_entrega_no_prazo.sql")).fetchone()

        assert resultado == (2, 1, 1, 50.0)
    finally:
        con.close()
