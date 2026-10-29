import duckdb
import pandas as pd
import pytest

import painel


def test_reais_pct_e_numero_formatam_dados_inventados():
    assert painel.reais(1234.56) == "R$ 1.234,56"
    assert painel.pct(12.345, 2) == "12,35%"
    assert painel.numero(987654, 0) == "987.654"


def test_ler_retorna_dataframe_e_fecha_conexao(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    con = duckdb.connect("olist.duckdb")
    con.execute("CREATE SCHEMA marts")
    con.execute("CREATE TABLE marts.exemplo AS SELECT 17 AS valor")
    con.close()

    dados = painel.ler(("exemplo",))

    assert dados["exemplo"].to_dict(orient="records") == [{"valor": 17}]
    escritor = duckdb.connect("olist.duckdb")
    try:
        escritor.execute("CREATE TABLE prova_escrita AS SELECT 1 AS valor")
        assert escritor.execute("SELECT COUNT(*) FROM prova_escrita").fetchone() == (1,)
    finally:
        escritor.close()


def test_mart_ausente_e_banco_ausente_sao_reportados(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    con = duckdb.connect("olist.duckdb")
    con.execute("CREATE SCHEMA marts")
    con.close()

    with pytest.raises(painel.MartsAusentesError) as erro_mart:
        painel.ler(("nao_existe",))

    assert erro_mart.value.nomes == ("nao_existe",)

    (tmp_path / "olist.duckdb").unlink()
    with pytest.raises(painel.BancoIndisponivelError):
        painel.ler(("qualquer",))


def _amostras_graficos():
    return {
        "vendas": pd.DataFrame(
            {
                "mes": pd.to_datetime(
                    [
                        "2017-01-01",  # Primeiro mês da série inventada.
                        "2017-02-01",  # Segundo mês para formar outro ponto.
                    ]
                ),
                "pedidos": [
                    1,  # Mês inicial para um ponto mensal.
                    2,  # Segundo mês para confirmar múltiplos pontos.
                ],
                "receita": [
                    10.0,  # Receita inventada do primeiro mês.
                    20.0,  # Receita inventada do segundo mês.
                ],
            }
        ),
        "categorias": pd.DataFrame(
            {
                "categoria": [
                    "a",  # Primeira categoria do gráfico.
                    "b",  # Segunda categoria do gráfico.
                ],
                "receita": [
                    20.0,  # Maior valor para testar a ordenação.
                    10.0,  # Menor valor para manter duas barras.
                ],
            }
        ),
        "pagamentos": pd.DataFrame(
            {
                "tipo": [
                    "cartao",  # Primeiro tipo de pagamento.
                    "boleto",  # Segundo tipo de pagamento.
                ],
                "pct_valor": [
                    60.0,  # Participação inventada do primeiro tipo.
                    40.0,  # Participação inventada do segundo tipo.
                ],
            }
        ),
        "tickets": pd.DataFrame(
            {
                "uf": ["SP", "PB"],  # Duas UFs para exercitar a ordenação.
                "ticket_medio": [
                    10.0,  # Ticket da primeira UF.
                    20.0,  # Ticket maior para a segunda UF.
                ],
            }
        ),
        "clientes": pd.DataFrame(
            {
                "uf": ["SP", "PB"],  # Duas UFs precisam virar dois pontos.
                "clientes": [
                    1,  # Contagem inventada para SP.
                    2,  # Contagem inventada para PB.
                ],
            }
        ),
        "notas": pd.DataFrame(
            {
                "categoria": ["a", "b"],  # Duas categorias avaliadas.
                "pedidos_avaliados": [1, 2],  # Volume inventado por categoria.
                "nota_media": [4.0, 2.0],  # Notas para ordenar pior primeiro.
                "posicao_pior": [2, 1],  # Posição definida pelo mart.
            }
        ),
        "vendedores": pd.DataFrame(
            {
                "posicao": [2, 1],  # Posições fora de ordem para testar sort.
                "pct_acumulado": [
                    100.0,  # Acumulado do segundo vendedor.
                    50.0,  # Acumulado do primeiro vendedor.
                ],
            }
        ),
    }


def test_grafico_vendas_mensais_tem_um_ponto_por_linha():
    dados = _amostras_graficos()["vendas"]
    figura = painel.grafico_vendas_mensais(dados)
    assert len(figura.data[0].x) == len(dados)


def test_grafico_top_categorias_tem_um_ponto_por_linha():
    dados = _amostras_graficos()["categorias"]
    figura = painel.grafico_top_categorias(dados)
    assert len(figura.data[0].y) == len(dados)


def test_grafico_mix_pagamento_tem_um_ponto_por_linha():
    dados = _amostras_graficos()["pagamentos"]
    figura = painel.grafico_mix_pagamento(dados)
    assert len(figura.data[0].x) == len(dados)


def test_grafico_ticket_por_uf_tem_um_ponto_por_linha():
    dados = _amostras_graficos()["tickets"]
    figura = painel.grafico_ticket_por_uf(dados)
    assert len(figura.data[0].y) == len(dados)


def test_grafico_clientes_por_uf_tem_um_ponto_por_linha():
    dados = _amostras_graficos()["clientes"]
    figura = painel.grafico_clientes_por_uf(dados)
    assert len(figura.data[0].y) == len(dados)


def test_grafico_nota_por_categoria_tem_um_ponto_por_linha():
    dados = _amostras_graficos()["notas"]
    figura = painel.grafico_nota_por_categoria(dados)
    assert len(figura.data[0].y) == len(dados)


def test_grafico_concentracao_vendedores_tem_um_ponto_por_linha():
    dados = _amostras_graficos()["vendedores"]
    figura = painel.grafico_concentracao_vendedores(dados)
    assert len(figura.data[0].x) == len(dados)
