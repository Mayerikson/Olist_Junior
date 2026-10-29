import datetime
from decimal import Decimal

import duckdb
import pytest

from pipeline import db, transformacao


def _criar_raw(tmp_path, monkeypatch, itens=()):
    caminho = tmp_path / "transformacao.duckdb"
    monkeypatch.setattr(db, "ARQUIVO_BANCO", caminho)
    con = duckdb.connect(str(caminho))
    try:
        con.execute("CREATE SCHEMA raw")
        for tabela, definicao in transformacao.TABELAS.items():
            colunas = ", ".join(
                f'"{origem}" VARCHAR' for origem, _, _ in definicao["colunas"]
            )
            con.execute(f'CREATE TABLE raw."{tabela}" ({colunas})')
        if itens:
            marcadores = ", ".join("?" for _ in transformacao.TABELAS["itens_pedido"]["colunas"])
            con.executemany(
                f"INSERT INTO raw.itens_pedido VALUES ({marcadores})",
                itens,
            )
    finally:
        con.close()
    return caminho


def test_duplicata_exata_sai_e_tipos_de_data_e_dinheiro_sao_convertidos(
    tmp_path, monkeypatch
):
    linha = (
        "pedido-1",
        "1",
        "produto-1",
        None,  # Nulo original que refined deve preservar sem corrigir.
        "2017-02-03 15:04:05",
        "12.30",
        "2.50",
    )  # Uma linha inventada, repetida exatamente para validar DISTINCT.
    caminho = _criar_raw(tmp_path, monkeypatch, (linha, linha))

    transformacao.main()

    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute(
            "SELECT pedido_id, vendedor_id, preco, frete, data_limite_envio "
            "FROM refined.itens_pedido"
        ).fetchone() == (
            "pedido-1",
            None,
            Decimal("12.30"),
            Decimal("2.50"),
            datetime.datetime(2017, 2, 3, 15, 4, 5),
        )
        tipos = {
            linha[0]: linha[1]
            for linha in con.execute("DESCRIBE refined.itens_pedido").fetchall()
        }
        assert tipos["data_limite_envio"] == "TIMESTAMP"
        assert tipos["preco"] == "DECIMAL(10,2)"
        assert tipos["frete"] == "DECIMAL(10,2)"
    finally:
        con.close()


def test_valor_que_nao_converte_encerra_sem_criar_refined(tmp_path, monkeypatch):
    linha = (
        "pedido-1",
        "1",
        "produto-1",
        "vendedor-1",
        "2017-02-03 15:04:05",
        "nao-e-dinheiro",
        "2.50",
    )  # O preço deliberadamente inválido deve falhar, não virar NULL.
    caminho = _criar_raw(tmp_path, monkeypatch, (linha,))

    with pytest.raises(SystemExit) as erro:
        transformacao.main()

    assert erro.value.code == 1
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute(
            "SELECT COUNT(*) FROM information_schema.schemata "
            "WHERE schema_name = 'refined'"
        ).fetchone() == (0,)
    finally:
        con.close()


def test_chave_com_conteudo_conflitante_encerra(tmp_path, monkeypatch):
    base = (
        "pedido-1",
        "1",
        "produto-1",
        "vendedor-1",
        "2017-02-03 15:04:05",
        "12.30",
        "2.50",
    )
    conflito = (*base[:5], "13.30", base[6])  # Mesma chave com outro preço.
    _criar_raw(tmp_path, monkeypatch, (base, conflito))

    with pytest.raises(SystemExit) as erro:
        transformacao.main()

    assert erro.value.code == 1


def test_tabela_raw_ausente_encerra(tmp_path, monkeypatch):
    caminho = tmp_path / "sem-raw.duckdb"
    monkeypatch.setattr(db, "ARQUIVO_BANCO", caminho)
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA raw")
    con.close()

    with pytest.raises(SystemExit) as erro:
        transformacao.main()

    assert erro.value.code == 1
