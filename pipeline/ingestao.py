"""Ingest the nine Olist CSV files into the raw DuckDB schema.

The explicit file-to-table map uses Portuguese names because they are the
vocabulary needed for later joins. Every input is checked before the database
opens so a missing file cannot silently leave a partial, misleading dataset.
The gzip files are read directly with declared UTF-8 rather than guessed
encoding; empty fields become null while other text is not normalized.
Disabling type inference keeps values such as CEPs with leading zeroes intact.
No rows, columns, or values are converted, corrected, or deduplicated because
those decisions belong at the raw-to-refined boundary. Replacing each table
makes reruns safe after mistakes, and database-side counts provide the actual
stored row totals used for verification. UTF-8 stdout keeps accents readable
in the Windows Command Prompt; closing the connection releases the file lock.
"""

import sys

import pandas as pd

from pipeline.db import PASTA_RAW, conectar, criar_schema, gravar

ARQUIVOS_TABELAS = (
    ("olist_orders_dataset.csv.gz", "pedidos"),
    ("olist_order_items_dataset.csv.gz", "itens_pedido"),
    ("olist_order_payments_dataset.csv.gz", "pagamentos"),
    ("olist_order_reviews_dataset.csv.gz", "avaliacoes"),
    ("olist_customers_dataset.csv.gz", "clientes"),
    ("olist_sellers_dataset.csv.gz", "vendedores"),
    ("olist_products_dataset.csv.gz", "produtos"),
    ("product_category_name_translation.csv.gz", "traducao_categorias"),
    ("olist_geolocation_dataset.csv.gz", "geolocalizacao"),
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    ausentes = [
        arquivo
        for arquivo, _ in ARQUIVOS_TABELAS
        if not (PASTA_RAW / arquivo).is_file()
    ]
    if ausentes:
        print(f"Arquivos ausentes em {PASTA_RAW}:")
        for arquivo in ausentes:
            print(f"  - {arquivo}")
        raise SystemExit(1)

    con = conectar()
    try:
        criar_schema(con, "raw")
        total = 0
        for arquivo, tabela in ARQUIVOS_TABELAS:
            df = pd.read_csv(
                PASTA_RAW / arquivo,
                encoding="utf-8",
                dtype=str,
                keep_default_na=False,
                na_values=[""],
                skip_blank_lines=False,
            )
            quantidade = gravar(con, df, "raw", tabela)
            total += quantidade
            print(f"raw.{tabela}: {quantidade:,}".replace(",", "."))
        print(f"Total: {total:,}".replace(",", "."))
    finally:
        con.close()


if __name__ == "__main__":
    main()
