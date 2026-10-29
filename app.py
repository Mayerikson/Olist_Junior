"""Página Streamlit do painel Olist."""

from pathlib import Path

import pandas as pd
import streamlit as st

from painel import (
    BancoIndisponivelError,
    MartsAusentesError,
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


@st.cache_data
def carregar_dados() -> dict[str, pd.DataFrame]:
    return ler(MARTS)


st.set_page_config(page_title="Olist · visão da operação", layout="wide")

cabecalho = st.columns([2, 3])
with cabecalho[0]:
    st.title("Olist · visão da operação")

if not Path("olist.duckdb").is_file():
    st.error(
        "Banco olist.duckdb não encontrado. "
        "Execute: uv run python -m pipeline.marts"
    )
    st.stop()

try:
    dados = carregar_dados()
except BancoIndisponivelError as erro:
    st.error(
        "Não foi possível abrir olist.duckdb. Feche outro processo que "
        "esteja usando o banco (por exemplo, ui.py) e clique em "
        f"Recarregar dados. Detalhe: {erro}"
    )
    st.stop()
except MartsAusentesError as erro:
    st.error(
        f"Marts ausentes: {', '.join(erro.nomes)}. "
        "Execute: uv run python -m pipeline.marts"
    )
    st.stop()

with cabecalho[1]:
    meses = dados["vendas_mensais"]["mes"].to_list()
    inicio_padrao = pd.Timestamp(2017, 1, 1)
    fim_padrao = pd.Timestamp(2018, 8, 1)
    if inicio_padrao not in meses or fim_padrao not in meses:
        st.error(
            "O mart vendas_mensais precisa conter jan/2017 e ago/2018 "
            "para aplicar o período padrão."
        )
        st.stop()
    inicio, fim = st.select_slider(
        "Período",
        options=meses,
        value=(inicio_padrao, fim_padrao),
        format_func=mes_legivel,
    )
    st.caption("os cartões valem para o período inteiro")
    if st.button("Recarregar dados"):
        carregar_dados.clear()
        st.rerun()

kpis = dados["kpis"].iloc[0]
clientes_uma_compra = dados["recompra"].loc[
    dados["recompra"]["pedidos_por_cliente"] == 1,
    "pct_clientes",
].iloc[0]
recompra_pct = 100 - clientes_uma_compra
cartoes = st.columns(7)
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
        pct(recompra_pct, 2),
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
for coluna, (rotulo, valor, definicao) in zip(cartoes, metricas):
    coluna.metric(rotulo, valor, help=definicao)

vendas = dados["vendas_mensais"]
vendas_filtradas = vendas.loc[
    (vendas["mes"] >= inicio) & (vendas["mes"] <= fim)
]
st.plotly_chart(grafico_vendas_mensais(vendas_filtradas), width="stretch")

faixa_tres = st.columns(3)
with faixa_tres[0]:
    st.plotly_chart(
        grafico_top_categorias(dados["top_categorias"]),
        width="stretch",
    )
with faixa_tres[1]:
    st.plotly_chart(
        grafico_mix_pagamento(dados["mix_pagamento"]),
        width="stretch",
    )
with faixa_tres[2]:
    st.plotly_chart(
        grafico_ticket_por_uf(dados["ticket_medio_por_estado"]),
        width="stretch",
    )

faixa_quatro = st.columns(3)
with faixa_quatro[0]:
    st.plotly_chart(
        grafico_clientes_por_uf(dados["clientes_por_uf"]),
        width="stretch",
    )
with faixa_quatro[1]:
    st.plotly_chart(
        grafico_nota_por_categoria(dados["nota_por_categoria"]),
        width="stretch",
    )
with faixa_quatro[2]:
    st.plotly_chart(
        grafico_concentracao_vendedores(dados["vendedores_pareto"]),
        width="stretch",
    )
