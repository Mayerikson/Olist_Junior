from datetime import datetime

import duckdb

import relatorio


def _criar_marts(caminho):
    con = duckdb.connect(str(caminho))
    try:
        con.execute("CREATE SCHEMA marts")
        con.execute(
            "CREATE TABLE marts.vendas_mensais AS "
            # Mês fora do período para conferir o recorte no relatório.
            "SELECT DATE '2016-12-01' AS mes, 1 AS pedidos, 9.00 AS receita "
            # Janeiro inicial do intervalo padrão exibido.
            "UNION ALL SELECT DATE '2017-01-01', 2, 30.00 "
            # Agosto final do intervalo padrão exibido.
            "UNION ALL SELECT DATE '2018-08-01', 3, 40.00"
        )
        con.execute(
            "CREATE TABLE marts.top_categorias AS "
            "SELECT * FROM (VALUES "
            # Categoria com maior receita para a primeira barra.
            "('categoria-a', 2, 2, 30.00), "
            # Categoria menor para formar a segunda barra.
            "('categoria-b', 1, 1, 10.00)) "
            "AS t(categoria, pedidos, itens, receita)"
        )
        con.execute(
            "CREATE TABLE marts.entrega_no_prazo AS "
            # Linha única de entrega, necessária para o cartão No prazo.
            "SELECT 2 AS entregues, 1 AS no_prazo, 1 AS atrasados, 50.0 AS pct_no_prazo"
        )
        con.execute(
            "CREATE TABLE marts.nota_por_categoria AS "
            "SELECT * FROM (VALUES "
            # Pior nota para aparecer primeiro no gráfico.
            "('categoria-a', 2, 3.0, 1), "
            # Nota melhor para formar o segundo ponto.
            "('categoria-b', 1, 4.0, 2)) "
            "AS t(categoria, pedidos_avaliados, nota_media, posicao_pior)"
        )
        con.execute(
            "CREATE TABLE marts.recompra AS "
            "SELECT * FROM (VALUES "
            # Maioria com uma compra fornece o complemento do cartão.
            "(1, 9, 90.0), "
            # Grupo de recompra para formar uma tabela com mais de uma linha.
            "(2, 1, 10.0)) "
            "AS t(pedidos_por_cliente, clientes, pct_clientes)"
        )
        con.execute(
            "CREATE TABLE marts.ticket_medio_por_estado AS "
            "SELECT * FROM (VALUES "
            # Ticket menor para uma UF no gráfico.
            "('SP', 1, 10.0), "
            # Ticket maior para outra UF no gráfico.
            "('PB', 1, 20.0)) "
            "AS t(uf, pedidos, ticket_medio)"
        )
        con.execute(
            "CREATE TABLE marts.mix_pagamento AS "
            "SELECT * FROM (VALUES "
            # Pagamento predominante inventado para o primeiro tipo.
            "('cartao', 1, 1, 30.00, 75.0), "
            # Segundo tipo para compor a distribuição.
            "('boleto', 1, 1, 10.00, 25.0)) "
            "AS t(tipo, pagamentos, pedidos, valor, pct_valor)"
        )
        con.execute(
            "CREATE TABLE marts.vendedores_pareto AS "
            "SELECT * FROM (VALUES "
            # Primeiro vendedor inventado, com receita maior.
            "('v1', 'SP', 30.0, 1, 75.0), "
            # Segundo vendedor leva o acumulado ao total.
            "('v2', 'PB', 10.0, 2, 100.0)) "
            "AS t(vendedor_id, uf, receita, posicao, pct_acumulado)"
        )
        con.execute(
            "CREATE TABLE marts.kpis AS "
            # Linha de indicadores inventados para os sete cartões.
            "SELECT 20.0 AS ticket_medio, 10.0 AS ticket_mediana, "
            "5.0 AS pct_frete, 0.5 AS pct_cancelados, "
            "3.0 AS dias_entrega, 2.0 AS dias_entrega_mediana, "
            "4.0 AS nota_media"
        )
        con.execute(
            "CREATE TABLE marts.clientes_por_uf AS "
            "SELECT * FROM (VALUES "
            # UF com mais clientes no exemplo do gráfico.
            "('SP', 2), "
            # Segunda UF para formar outra barra.
            "('PB', 1)) AS t(uf, clientes)"
        )
    finally:
        con.close()


def test_gera_relatorio_em_tmp_path_e_so_muda_o_rodape(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(relatorio, "__file__", str(tmp_path / "relatorio.py"))
    _criar_marts(tmp_path / "olist.duckdb")

    class Relogio:
        valor = datetime(2026, 10, 25, 14, 3)

        @classmethod
        def now(cls):
            return cls.valor

    monkeypatch.setattr(relatorio, "datetime", Relogio)
    relatorio.main()
    caminho = tmp_path / "relatorio.html"
    primeiro = caminho.read_text(encoding="utf-8")
    Relogio.valor = datetime(2026, 10, 25, 14, 4)
    relatorio.main()
    segundo = caminho.read_text(encoding="utf-8")

    rodape_1 = "<footer>Dados de 25/10/2026 14:03</footer>"
    rodape_2 = "<footer>Dados de 25/10/2026 14:04</footer>"
    assert caminho.is_file()
    assert rodape_1 in primeiro
    assert rodape_2 in segundo
    assert primeiro.replace(rodape_1, "<footer>DATA</footer>") == segundo.replace(
        rodape_2, "<footer>DATA</footer>"
    )
    for valor in (
        "R$ 20,00",
        "0,50%",
        "5,0%",
        "10,00%",
        "50,0%",
        "3,0",
        "4,00",
    ):
        assert valor in primeiro
    assert caminho.stat().st_size < 200 * 1024
