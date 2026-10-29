"""Spec do painel da operação Olist.

Fonte da verdade: a especificação do painel. Este módulo não importa
Streamlit e concentra leitura, formatação e figuras para também permitir
reaproveitamento em relatório HTML.

Leitura: ler(marts) devolve um dicionário de DataFrames e, para cada nome,
executa somente SELECT * FROM marts.<nome>. A conexão usa
duckdb.connect("olist.duckdb", read_only=True) e é fechada dentro da função,
pois uma conexão aberta impede o pipeline de gravar enquanto o painel roda.

Cálculos: não há agregações nem operações entre colunas neste módulo ou em
app.py. Os números novos pertencem a um SQL de mart. A única exceção é a
recompra, exibida como 100 menos pct_clientes da linha pedidos_por_cliente = 1,
porque o mart 05 armazena o complemento.

Formato: reais, pct e numero são funções puras e não dependem da localidade
do sistema. Cada gráfico tem uma função que recebe um DataFrame e devolve uma
figura Plotly, mantendo a mesma visualização disponível para outros relatórios.

Período: a seleção recorta somente as linhas do gráfico mensal; cartões e
demais figuras continuam representando o período completo. Assim, a seleção
não recalcula regras de negócio fora do SQL.

Layout e cache: app.py usa layout wide, sete cartões e os gráficos definidos
na spec. A leitura é armazenada por st.cache_data e o botão de recarga limpa
esse cache. Banco ausente ou mart necessário ausente deve ser informado na
página com o comando para executar pipeline.marts.
"""

from collections.abc import Sequence

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

COR = "#2864A5"


class MartsAusentesError(Exception):
    """Indica quais tabelas necessárias não foram encontradas."""

    def __init__(self, nomes: Sequence[str]) -> None:
        self.nomes = tuple(nomes)
        super().__init__(", ".join(self.nomes))


class BancoIndisponivelError(Exception):
    """Indica que DuckDB não conseguiu abrir o arquivo do banco."""


def ler(marts: Sequence[str]) -> dict[str, pd.DataFrame]:
    """Lê os marts indicados usando uma conexão curta, somente para leitura."""
    try:
        con = duckdb.connect("olist.duckdb", read_only=True)
    except duckdb.IOException as erro:
        raise BancoIndisponivelError(str(erro)) from erro
    dados: dict[str, pd.DataFrame] = {}
    ausentes = []
    try:
        for nome in marts:
            try:
                dados[nome] = con.execute(
                    f"SELECT * FROM marts.{nome}"
                ).fetchdf()
            except duckdb.CatalogException:
                ausentes.append(nome)
        if ausentes:
            raise MartsAusentesError(ausentes)
        return dados
    finally:
        con.close()


def numero(valor: float, casas: int = 0) -> str:
    """Formata com ponto de milhar e vírgula decimal, sem locale do sistema."""
    formatado = f"{valor:,.{casas}f}"
    inteiro, _, decimal = formatado.partition(".")
    resultado = inteiro.replace(",", ".")
    return f"{resultado},{decimal}" if decimal else resultado


def reais(valor: float, casas: int = 2) -> str:
    """Formata um valor monetário em reais."""
    return f"R$ {numero(valor, casas)}"


def pct(valor: float, casas: int = 1) -> str:
    """Formata um percentual já expresso em pontos percentuais."""
    return f"{numero(valor, casas)}%"


def mes_legivel(valor: pd.Timestamp) -> str:
    """Retorna o mês com abreviação portuguesa, sem depender de locale."""
    meses = (
        "jan", "fev", "mar", "abr", "mai", "jun",
        "jul", "ago", "set", "out", "nov", "dez",
    )
    return f"{meses[valor.month - 1]}/{valor.year}"


def _estilizar(
    figura: go.Figure,
    titulo: str,
    eixo_x: str,
    eixo_y: str,
) -> go.Figure:
    figura.update_layout(
        title=titulo,
        template="plotly_white",
        showlegend=False,
        height=360,
        margin={"l": 12, "r": 12, "t": 56, "b": 24},
    )
    figura.update_xaxes(title_text=eixo_x)
    figura.update_yaxes(title_text=eixo_y)
    return figura


def grafico_vendas_mensais(df: pd.DataFrame) -> go.Figure:
    """Cria a série mensal de faturamento com marcadores."""
    df_ordenado = df.sort_values("mes")
    figura = px.line(df_ordenado, x="mes", y="receita", markers=True)
    figura.update_traces(line_color=COR, marker_color=COR)
    figura.update_xaxes(
        tickmode="array",
        tickvals=df_ordenado["mes"],
        ticktext=[mes_legivel(mes) for mes in df_ordenado["mes"]],
        tickangle=-45,
    )
    return _estilizar(
        figura,
        "01 · Faturamento mensal",
        "Mês",
        "Receita (R$)",
    )


def grafico_top_categorias(df: pd.DataFrame) -> go.Figure:
    """Cria barras horizontais para as dez categorias de maior receita."""
    top = df.sort_values("receita", ascending=False).head(10)
    figura = px.bar(top, x="receita", y="categoria", orientation="h")
    figura.update_traces(marker_color=COR)
    figura.update_yaxes(autorange="reversed")
    return _estilizar(
        figura,
        "02 · Receita por categoria",
        "Receita (R$)",
        "Categoria",
    )


def grafico_mix_pagamento(df: pd.DataFrame) -> go.Figure:
    """Cria barras para a participação no valor pago por tipo."""
    figura = px.bar(df, x="tipo", y="pct_valor")
    figura.update_traces(marker_color=COR)
    return _estilizar(
        figura,
        "07 · Mix de pagamento",
        "Tipo de pagamento",
        "Participação no valor pago (%)",
    )


def grafico_ticket_por_uf(df: pd.DataFrame) -> go.Figure:
    """Cria barras horizontais de ticket médio, da maior UF para a menor."""
    ordenado = df.sort_values("ticket_medio", ascending=False)
    figura = px.bar(
        ordenado,
        x="ticket_medio",
        y="uf",
        orientation="h",
    )
    figura.update_traces(marker_color=COR)
    figura.update_yaxes(autorange="reversed")
    return _estilizar(
        figura,
        "06 · Ticket médio por UF",
        "Ticket médio (R$)",
        "UF",
    )


def grafico_clientes_por_uf(df: pd.DataFrame) -> go.Figure:
    """Cria barras horizontais de clientes por UF, em ordem decrescente."""
    ordenado = df.sort_values("clientes", ascending=False)
    figura = px.bar(ordenado, x="clientes", y="uf", orientation="h")
    figura.update_traces(marker_color=COR)
    figura.update_yaxes(autorange="reversed")
    return _estilizar(
        figura,
        "12 · Clientes por UF",
        "Clientes",
        "UF",
    )


def grafico_nota_por_categoria(df: pd.DataFrame) -> go.Figure:
    """Cria pontos para as dez categorias de pior nota."""
    piores = df.sort_values("posicao_pior").head(10)
    figura = px.scatter(piores, x="nota_media", y="categoria")
    figura.update_traces(marker_color=COR, marker_size=10)
    figura.update_yaxes(autorange="reversed")
    return _estilizar(
        figura,
        "04 · Nota por categoria",
        "Nota média (0–5)",
        "Categoria",
    )


def grafico_concentracao_vendedores(df: pd.DataFrame) -> go.Figure:
    """Cria a curva de receita acumulada dos vendedores."""
    ordenado = df.sort_values("posicao")
    figura = px.line(ordenado, x="posicao", y="pct_acumulado")
    figura.update_traces(line_color=COR)
    figura.add_hline(y=80, line_dash="dash", line_color=COR)
    return _estilizar(
        figura,
        "09 · Concentração de vendedores",
        "Posição do vendedor",
        "Receita acumulada (%)",
    )
