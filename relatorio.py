"""Gera relatorio.html a partir dos marts e das figuras reutilizáveis do painel."""

import sys
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from painel import (
    grafico_clientes_por_uf,
    grafico_concentracao_vendedores,
    grafico_mix_pagamento,
    grafico_nota_por_categoria,
    grafico_ticket_por_uf,
    grafico_top_categorias,
    grafico_vendas_mensais,
    ler,
    mes_legivel,
    numero,
    pct,
    reais,
)

MARTS = (
    "vendas_mensais",
    "top_categorias",
    "entrega_no_prazo",
    "nota_por_categoria",
    "recompra",
    "ticket_medio_por_estado",
    "mix_pagamento",
    "vendedores_pareto",
    "kpis",
    "clientes_por_uf",
)


def _cartao(rotulo: str, valor: str, definicao: str) -> str:
    return (
        '<article class="card">'
        f"<h2>{escape(rotulo)}</h2>"
        f'<p class="value">{escape(valor)}</p>'
        f"<p>{escape(definicao)}</p>"
        "</article>"
    )


def _grafico_html(figura: go.Figure, indice: int) -> str:
    return figura.to_html(
        full_html=False,
        include_plotlyjs="cdn" if indice == 1 else False,
        div_id=f"g{indice:02}",
    )


def _montar_html(dados: dict[str, pd.DataFrame], gerado_em: datetime) -> str:
    kpis = dados["kpis"].iloc[0]
    clientes_uma_compra = dados["recompra"].loc[
        dados["recompra"]["pedidos_por_cliente"] == 1,
        "pct_clientes",
    ].iloc[0]
    metricas = (
        ("Ticket médio", reais(kpis["ticket_medio"]), "Receita média por pedido válido."),
        (
            "Cancelados · % de todos os pedidos",
            pct(kpis["pct_cancelados"], 2),
            "Percentual de todos os pedidos com status cancelado.",
        ),
        (
            "Peso do frete",
            pct(kpis["pct_frete"], 1),
            "Percentual do valor total pago que corresponde ao frete.",
        ),
        (
            "Recompra",
            pct(100 - clientes_uma_compra, 2),
            "Percentual de clientes com mais de um pedido válido.",
        ),
        (
            "No prazo",
            pct(dados["entrega_no_prazo"].iloc[0]["pct_no_prazo"], 1),
            "Percentual de pedidos entregues até a data prevista.",
        ),
        (
            "Dias até entregar",
            numero(kpis["dias_entrega"], 1),
            "Média de dias entre compra e entrega.",
        ),
        (
            "Nota média",
            numero(kpis["nota_media"], 2),
            "Média das avaliações dos pedidos.",
        ),
    )
    cartoes = "\n".join(
        _cartao(rotulo, valor, definicao)
        for rotulo, valor, definicao in metricas
    )

    inicio = pd.Timestamp(2017, 1, 1)
    fim = pd.Timestamp(2018, 8, 1)
    vendas = dados["vendas_mensais"]
    vendas_periodo = vendas.loc[(vendas["mes"] >= inicio) & (vendas["mes"] <= fim)]
    titulo_periodo = f"{mes_legivel(inicio)} a {mes_legivel(fim)}"
    figura_vendas = grafico_vendas_mensais(vendas_periodo)
    figura_vendas.update_layout(
        title=f"01 · Faturamento mensal ({titulo_periodo})"
    )

    figuras = (
        figura_vendas,
        grafico_top_categorias(dados["top_categorias"]),
        grafico_mix_pagamento(dados["mix_pagamento"]),
        grafico_ticket_por_uf(dados["ticket_medio_por_estado"]),
        grafico_clientes_por_uf(dados["clientes_por_uf"]),
        grafico_nota_por_categoria(dados["nota_por_categoria"]),
        grafico_concentracao_vendedores(dados["vendedores_pareto"]),
    )
    graficos = [_grafico_html(figura, i) for i, figura in enumerate(figuras, 1)]
    faixa_tres = "\n".join(
        f'<section class="chart">{grafico}</section>'
        for grafico in graficos[1:4]
    )
    faixa_quatro = "\n".join(
        f'<section class="chart">{grafico}</section>'
        for grafico in graficos[4:7]
    )
    rodape = gerado_em.strftime("Dados de %d/%m/%Y %H:%M")

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Olist · visão da operação</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; color: #263648; }}
    body {{ margin: 0; padding: 32px; background: #f7f9fc; }}
    main {{ max-width: 1440px; margin: 0 auto; }}
    h1 {{ margin: 0 0 24px; font-size: 30px; }}
    .cards {{ display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 12px; }}
    .card, .chart {{ background: white; border: 1px solid #e4e9f0; border-radius: 8px; }}
    .card {{ padding: 16px; }}
    .card h2 {{ margin: 0 0 12px; font-size: 14px; }}
    .card p {{ margin: 0; font-size: 12px; color: #657387; }}
    .card .value {{ margin-bottom: 8px; font-size: 22px; font-weight: 700; color: #263648; }}
    .chart {{ min-width: 0; padding: 8px; }}
    .full {{ margin-top: 16px; }}
    .grid-three {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-top: 16px; }}
    footer {{ margin-top: 24px; color: #657387; font-size: 13px; text-align: right; }}
    @media (max-width: 1000px) {{
      .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .grid-three {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>Olist · visão da operação</h1>
    <section class="cards">{cartoes}</section>
    <section class="chart full">{graficos[0]}</section>
    <section class="grid-three">{faixa_tres}</section>
    <section class="grid-three">{faixa_quatro}</section>
    <footer>{rodape}</footer>
  </main>
</body>
</html>
"""


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    dados = ler(MARTS)
    caminho = Path(__file__).resolve().parent / "relatorio.html"
    caminho.write_text(
        _montar_html(dados, datetime.now()),
        encoding="utf-8",
    )
    tamanho_kb = caminho.stat().st_size / 1024
    print(f"Relatório: {caminho}")
    print(f"Tamanho: {numero(tamanho_kb, 1)} KB")


if __name__ == "__main__":
    main()
