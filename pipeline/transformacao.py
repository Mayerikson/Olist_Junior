"""Spec da transformação raw -> refined.

O script lê oito tabelas de raw e materializa oito tabelas em refined.
Geolocalização fica fora porque nenhum mart do curso a consome; não se
transforma dado sem uso definido. As colunas seguem integralmente o mapa
português abaixo para que os nomes usados nos JOINs sejam previsíveis.

Datas e medidas recebem tipos úteis para consultas, mas identificadores e
demais atributos continuam VARCHAR: CEP, por exemplo, pode começar com zero
e não representa uma quantidade. Datas usam formatos explícitos; dinheiro
usa DECIMAL para preservar centavos. Conversões são estritas porque um erro
não pode virar um NULL indistinguível de um NULL original.

Chaves são declaradas por tabela. Cópias idênticas são redundância e podem
ser removidas; linhas com a mesma chave e conteúdo diferente exigem uma
decisão humana, então interrompem a execução e são exibidas. Nulos e
anomalias de negócio permanecem porque refined não corrige fatos nem escolhe
regras de negócio para os marts.

Cada tabela é recriada, nunca anexada, para que reexecuções sejam
idempotentes. As contagens de entrada, saída, duplicatas e nulos vêm do
DuckDB para deixar visível o que mudou; o banco é a fonte dos números.

Mapa literal de colunas e chaves:
    pedidos: order_id->pedido_id, customer_id->cliente_id,
      order_status->status, order_purchase_timestamp->data_compra,
      order_approved_at->data_aprovacao,
      order_delivered_carrier_date->data_envio,
      order_delivered_customer_date->data_entrega,
      order_estimated_delivery_date->data_entrega_prevista.
      Chave: pedido_id.
    itens_pedido: order_id->pedido_id, order_item_id->item_seq,
      product_id->produto_id, seller_id->vendedor_id,
      shipping_limit_date->data_limite_envio, price->preco,
      freight_value->frete. Chave: (pedido_id, item_seq).
    pagamentos: order_id->pedido_id, payment_sequential->pagamento_seq,
      payment_type->tipo, payment_installments->parcelas,
      payment_value->valor. Chave: (pedido_id, pagamento_seq).
    clientes: customer_id->cliente_id,
      customer_unique_id->cliente_unico_id,
      customer_zip_code_prefix->cep_prefixo, customer_city->cidade,
      customer_state->uf. Chave: cliente_id.
    vendedores: seller_id->vendedor_id,
      seller_zip_code_prefix->cep_prefixo, seller_city->cidade,
      seller_state->uf. Chave: vendedor_id.
    produtos: product_id->produto_id, product_category_name->categoria,
      product_name_lenght->tamanho_nome,
      product_description_lenght->tamanho_descricao,
      product_photos_qty->qtd_fotos, product_weight_g->peso_g,
      product_length_cm->comprimento_cm, product_height_cm->altura_cm,
      product_width_cm->largura_cm. Chave: produto_id.
    traducao_categorias: product_category_name->categoria,
      product_category_name_english->categoria_en. Chave: categoria.
    avaliacoes: review_id->avaliacao_id, order_id->pedido_id,
      review_score->nota, review_comment_title->titulo,
      review_comment_message->comentario,
      review_creation_date->data_criacao,
      review_answer_timestamp->data_resposta.
      Chave: (avaliacao_id, pedido_id), pois avaliacao_id sozinho pode se
      repetir em pedidos diferentes.
"""

import sys

import duckdb

from pipeline.db import conectar, criar_schema

FORMATO_DATA_HORA = "%Y-%m-%d %H:%M:%S"

# Cada coluna registra origem, nome final e tipo DuckDB; None preserva VARCHAR.
TABELAS = {
    "pedidos": {
        "chave": ("order_id",),
        "colunas": (
            ("order_id", "pedido_id", None),
            ("customer_id", "cliente_id", None),
            ("order_status", "status", None),
            ("order_purchase_timestamp", "data_compra", "TIMESTAMP"),
            ("order_approved_at", "data_aprovacao", "TIMESTAMP"),
            ("order_delivered_carrier_date", "data_envio", "TIMESTAMP"),
            ("order_delivered_customer_date", "data_entrega", "TIMESTAMP"),
            ("order_estimated_delivery_date", "data_entrega_prevista", "DATE"),
        ),
    },
    "itens_pedido": {
        "chave": ("order_id", "order_item_id"),
        "colunas": (
            ("order_id", "pedido_id", None),
            ("order_item_id", "item_seq", "INTEGER"),
            ("product_id", "produto_id", None),
            ("seller_id", "vendedor_id", None),
            ("shipping_limit_date", "data_limite_envio", "TIMESTAMP"),
            ("price", "preco", "DECIMAL(10,2)"),
            ("freight_value", "frete", "DECIMAL(10,2)"),
        ),
    },
    "pagamentos": {
        "chave": ("order_id", "payment_sequential"),
        "colunas": (
            ("order_id", "pedido_id", None),
            ("payment_sequential", "pagamento_seq", "INTEGER"),
            ("payment_type", "tipo", None),
            ("payment_installments", "parcelas", "INTEGER"),
            ("payment_value", "valor", "DECIMAL(10,2)"),
        ),
    },
    "clientes": {
        "chave": ("customer_id",),
        "colunas": (
            ("customer_id", "cliente_id", None),
            ("customer_unique_id", "cliente_unico_id", None),
            ("customer_zip_code_prefix", "cep_prefixo", None),
            ("customer_city", "cidade", None),
            ("customer_state", "uf", None),
        ),
    },
    "vendedores": {
        "chave": ("seller_id",),
        "colunas": (
            ("seller_id", "vendedor_id", None),
            ("seller_zip_code_prefix", "cep_prefixo", None),
            ("seller_city", "cidade", None),
            ("seller_state", "uf", None),
        ),
    },
    "produtos": {
        "chave": ("product_id",),
        "colunas": (
            ("product_id", "produto_id", None),
            ("product_category_name", "categoria", None),
            ("product_name_lenght", "tamanho_nome", "INTEGER"),
            ("product_description_lenght", "tamanho_descricao", "INTEGER"),
            ("product_photos_qty", "qtd_fotos", "INTEGER"),
            ("product_weight_g", "peso_g", "INTEGER"),
            ("product_length_cm", "comprimento_cm", "INTEGER"),
            ("product_height_cm", "altura_cm", "INTEGER"),
            ("product_width_cm", "largura_cm", "INTEGER"),
        ),
    },
    "traducao_categorias": {
        "chave": ("product_category_name",),
        "colunas": (
            ("product_category_name", "categoria", None),
            ("product_category_name_english", "categoria_en", None),
        ),
    },
    "avaliacoes": {
        "chave": ("review_id", "order_id"),
        "colunas": (
            ("review_id", "avaliacao_id", None),
            ("order_id", "pedido_id", None),
            ("review_score", "nota", "INTEGER"),
            ("review_comment_title", "titulo", None),
            ("review_comment_message", "comentario", None),
            ("review_creation_date", "data_criacao", "DATE"),
            ("review_answer_timestamp", "data_resposta", "TIMESTAMP"),
        ),
    },
}


class TransformacaoInvalida(Exception):
    """Erro de dados que precisa ser mostrado antes de encerrar."""


def _identificador(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def _formatar_quantidade(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def _expressao_conversao(coluna: str, tipo: str) -> str:
    origem = _identificador(coluna)
    if tipo in {"TIMESTAMP", "DATE"}:
        expressao = f"strptime({origem}, '{FORMATO_DATA_HORA}')"
        return f"CAST({expressao} AS DATE)" if tipo == "DATE" else expressao
    return f"CAST({origem} AS {tipo})"


def _validar_entradas(con: duckdb.DuckDBPyConnection) -> None:
    existentes = {
        linha[0]
        for linha in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'raw'"
        ).fetchall()
    }
    ausentes = sorted(set(TABELAS) - existentes)
    if ausentes:
        faltantes = ", ".join(f"raw.{nome}" for nome in ausentes)
        raise TransformacaoInvalida(
            f"Tabelas de entrada ausentes: {faltantes}. "
            "Rode: uv run python -m pipeline.ingestao"
        )

    for tabela, definicao in TABELAS.items():
        colunas_raw = [
            linha[0]
            for linha in con.execute(
                f"DESCRIBE SELECT * FROM raw.{_identificador(tabela)}"
            ).fetchall()
        ]
        colunas_spec = [coluna[0] for coluna in definicao["colunas"]]
        if colunas_raw != colunas_spec:
            raise TransformacaoInvalida(
                f"Colunas inesperadas em raw.{tabela}. "
                f"Esperadas: {colunas_spec}; encontradas: {colunas_raw}"
            )


def _validar_chaves(con: duckdb.DuckDBPyConnection) -> None:
    for tabela, definicao in TABELAS.items():
        colunas = [coluna[0] for coluna in definicao["colunas"]]
        chave = definicao["chave"]
        chave_sql = ", ".join(_identificador(coluna) for coluna in chave)
        linha_sql = ", ".join(_identificador(coluna) for coluna in colunas)
        conflitos = con.execute(
            f"SELECT {chave_sql} "
            f"FROM raw.{_identificador(tabela)} "
            f"GROUP BY {chave_sql} "
            f"HAVING COUNT(DISTINCT ({linha_sql})) > 1"
        ).fetchall()
        if not conflitos:
            continue

        print(f"Chaves repetidas com conteúdo diferente em raw.{tabela}:")
        condicao = " AND ".join(
            f"t.{_identificador(coluna)} IS NOT DISTINCT FROM ?"
            for coluna in chave
        )
        consulta = (
            f"SELECT {', '.join('t.' + _identificador(coluna) for coluna in colunas)} "
            f"FROM raw.{_identificador(tabela)} AS t WHERE {condicao}"
        )
        for valores_chave in conflitos:
            chave_exibida = dict(zip(chave, valores_chave))
            print(f"  chave: {chave_exibida}")
            linhas = con.execute(consulta, list(valores_chave)).fetchall()
            for linha in linhas:
                print(f"    {dict(zip(colunas, linha))}")
        raise TransformacaoInvalida(
            f"Resolva as chaves conflitantes em raw.{tabela}; "
            "nenhuma linha foi escolhida automaticamente."
        )


def _validar_conversoes(con: duckdb.DuckDBPyConnection) -> None:
    for tabela, definicao in TABELAS.items():
        for origem, _, tipo in definicao["colunas"]:
            if tipo is None:
                continue
            expressao = _expressao_conversao(origem, tipo)
            try:
                con.execute(
                    f"SELECT {expressao} FROM raw.{_identificador(tabela)}"
                )
            except duckdb.Error as erro:
                raise TransformacaoInvalida(
                    f"Falha de conversão em raw.{tabela}.{origem} "
                    f"para {tipo}. Exemplo/erro informado pelo DuckDB: {erro}"
                ) from erro


def _criar_tabelas_refined(con: duckdb.DuckDBPyConnection) -> int:
    criar_schema(con, "refined")
    total = 0
    for tabela, definicao in TABELAS.items():
        colunas = definicao["colunas"]
        projecoes = []
        for origem, destino, tipo in colunas:
            expressao = (
                _identificador(origem)
                if tipo is None
                else _expressao_conversao(origem, tipo)
            )
            projecoes.append(f"{expressao} AS {_identificador(destino)}")

        quantidade_entrada = con.execute(
            f"SELECT COUNT(*) FROM raw.{_identificador(tabela)}"
        ).fetchone()[0]
        con.execute(
            f"CREATE OR REPLACE TABLE refined.{_identificador(tabela)} AS "
            f"SELECT DISTINCT {', '.join(projecoes)} "
            f"FROM raw.{_identificador(tabela)}"
        )
        quantidade_saida = con.execute(
            f"SELECT COUNT(*) FROM refined.{_identificador(tabela)}"
        ).fetchone()[0]
        duplicatas = quantidade_entrada - quantidade_saida
        total += quantidade_saida

        print(
            f"refined.{tabela:<20} "
            f"{_formatar_quantidade(quantidade_entrada)} -> "
            f"{_formatar_quantidade(quantidade_saida)} linhas  "
            f"({_formatar_quantidade(duplicatas)} duplicatas)"
        )
        nulos = []
        for _, destino, _ in colunas:
            nome_sql = _identificador(destino)
            quantidade_nula = con.execute(
                f"SELECT COUNT(*) FILTER (WHERE {nome_sql} IS NULL) "
                f"FROM refined.{_identificador(tabela)}"
            ).fetchone()[0]
            if quantidade_nula:
                nulos.append(
                    f"{destino} {_formatar_quantidade(quantidade_nula)}"
                )
        if nulos:
            print(f"    nulos mantidos: {', '.join(nulos)}")

    return total


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    try:
        _validar_entradas(con)
        _validar_chaves(con)
        _validar_conversoes(con)
        con.execute("BEGIN TRANSACTION")
        try:
            total = _criar_tabelas_refined(con)
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        print(f"Total: {_formatar_quantidade(total)} linhas")
    except TransformacaoInvalida as erro:
        print(erro)
        raise SystemExit(1) from erro
    finally:
        con.close()


if __name__ == "__main__":
    main()
