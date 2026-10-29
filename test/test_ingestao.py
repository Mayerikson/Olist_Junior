import csv
import gzip

import duckdb
import pytest

from pipeline import db, ingestao


def _escrever_csv_gz(caminho, linhas):
    with gzip.open(caminho, "wt", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(("codigo", "campo_vazio"))
        escritor.writerows(linhas)


def test_csv_gz_vira_tabela_preservando_texto_e_linhas(tmp_path, monkeypatch):
    pasta_raw = tmp_path / "raw"
    pasta_raw.mkdir()
    banco = tmp_path / "teste.duckdb"
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta_raw)
    monkeypatch.setattr(db, "ARQUIVO_BANCO", banco)

    for indice, (arquivo, _) in enumerate(ingestao.ARQUIVOS_TABELAS):
        linhas = [
            # O CEP textual começa com zero; campo vazio deve virar NULL.
            ("00123", ""),
            # A segunda linha inventada confirma que a ingestão não deduplica.
            (f"linha-{indice}", "texto"),
        ]
        _escrever_csv_gz(pasta_raw / arquivo, linhas)

    ingestao.main()

    con = duckdb.connect(str(banco), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM raw.pedidos").fetchone() == (2,)
        assert con.execute(
            "SELECT codigo, campo_vazio FROM raw.pedidos ORDER BY codigo"
        ).fetchall() == [("00123", None), ("linha-0", "texto")]
        assert con.execute(
            "SELECT COUNT(*) FROM raw.geolocalizacao"
        ).fetchone() == (2,)
    finally:
        con.close()


def test_arquivo_faltando_encerra_antes_de_criar_banco(tmp_path, monkeypatch):
    pasta_raw = tmp_path / "raw"
    pasta_raw.mkdir()
    banco = tmp_path / "nao-criar.duckdb"
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta_raw)
    monkeypatch.setattr(db, "ARQUIVO_BANCO", banco)

    with pytest.raises(SystemExit) as erro:
        ingestao.main()

    assert erro.value.code == 1
    assert not banco.exists()
