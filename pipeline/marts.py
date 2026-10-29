"""Spec da materialização de sql/marts em tabelas do schema marts.

O script consulta apenas as oito tabelas de refined e nunca grava nelas nem
em raw, pois são camadas de entrada deste passo. A lista de tabelas esperadas
vem de pipeline.transformacao para não divergir da definição de refined.

O schema marts é removido e recriado em uma única transação a cada execução:
assim, arquivos SQL apagados também removem seus marts e qualquer falha
preserva integralmente o resultado da última execução bem-sucedida.

Cada arquivo sql/marts/*.sql, ordenado alfabeticamente, define por inteiro
uma tabela; o Python apenas remove espaços e um ponto e vírgula finais e
executa CREATE TABLE AS, pois regras de negócio pertencem ao SQL. O nome da
tabela é o nome do arquivo sem extensão e sem o prefixo NN_.

Todos os arquivos e nomes são validados antes de modificar o banco para
evitar execução parcial ou nomes de tabela ambíguos. Cada tabela deve ter
linhas: uma tabela vazia costuma indicar um JOIN sem correspondência e pode
fazer um dashboard parecer que o negócio parou. As contagens vêm do DuckDB,
para exibir o que foi realmente materializado. stdout usa UTF-8 para exibir
corretamente os caracteres em terminais do Windows.
"""

import re
import sys
from pathlib import Path

import duckdb

from pipeline.db import RAIZ_PROJETO, conectar
from pipeline.transformacao import TABELAS

PASTA_MARTS = RAIZ_PROJETO / "sql" / "marts"


class MartsInvalidos(Exception):
    """Erro de validação ou materialização a ser mostrado ao usuário."""


def _identificador(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def _formatar_quantidade(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def _validar_refined(con: duckdb.DuckDBPyConnection) -> None:
    existentes = {
        linha[0]
        for linha in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'refined'"
        ).fetchall()
    }
    ausentes = sorted(set(TABELAS) - existentes)
    if ausentes:
        faltantes = ", ".join(f"refined.{nome}" for nome in ausentes)
        raise MartsInvalidos(
            f"Tabelas de entrada ausentes: {faltantes}. "
            "Rode: uv run python -m pipeline.transformacao"
        )


def _listar_arquivos() -> list[tuple[Path, str]]:
    arquivos = sorted(PASTA_MARTS.glob("*.sql"), key=lambda arquivo: arquivo.name)
    if not arquivos:
        raise MartsInvalidos(f"Nenhum arquivo .sql encontrado em {PASTA_MARTS}")

    sem_prefixo = [
        arquivo.name
        for arquivo in arquivos
        if re.match(r"^\d{2}_", arquivo.name) is None
    ]
    if sem_prefixo:
        raise MartsInvalidos("Arquivos sem prefixo NN_: " + ", ".join(sem_prefixo))

    nomes_por_arquivo = [(arquivo, arquivo.stem[3:]) for arquivo in arquivos]
    arquivos_por_nome: dict[str, list[str]] = {}
    for arquivo, nome in nomes_por_arquivo:
        arquivos_por_nome.setdefault(nome.casefold(), []).append(arquivo.name)
    duplicados = [nomes for nomes in arquivos_por_nome.values() if len(nomes) > 1]
    if duplicados:
        lista = "; ".join(", ".join(nomes) for nomes in duplicados)
        raise MartsInvalidos(f"Arquivos com o mesmo nome de tabela: {lista}")

    return nomes_por_arquivo


def _ler_sql(arquivos: list[tuple[Path, str]]) -> list[tuple[Path, str, str]]:
    consultas = []
    for arquivo, tabela in arquivos:
        try:
            consulta = arquivo.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as erro:
            raise MartsInvalidos(f"Erro ao ler {arquivo.name}: {erro}") from erro
        if consulta.endswith(";"):
            consulta = consulta[:-1].rstrip()
        consultas.append((arquivo, tabela, consulta))
    return consultas


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    try:
        _validar_refined(con)
        arquivos = _listar_arquivos()
        consultas = _ler_sql(arquivos)

        resultados = []
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute("DROP SCHEMA IF EXISTS marts CASCADE")
            con.execute("CREATE SCHEMA marts")
            for arquivo, tabela, consulta in consultas:
                tabela_sql = _identificador(tabela)
                try:
                    con.execute(f"CREATE TABLE marts.{tabela_sql} AS {consulta}")
                    quantidade = con.execute(
                        f"SELECT COUNT(*) FROM marts.{tabela_sql}"
                    ).fetchone()[0]
                except duckdb.Error as erro:
                    raise MartsInvalidos(
                        f"Erro no arquivo {arquivo.name}: {erro}"
                    ) from erro
                if quantidade == 0:
                    raise MartsInvalidos(
                        f"Mart marts.{tabela} retornou zero linhas "
                        f"(arquivo {arquivo.name})."
                    )
                resultados.append((tabela, quantidade))
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise

        total = 0
        for tabela, quantidade in resultados:
            total += quantidade
            nome = f"marts.{tabela}"
            unidade_linha = "linha" if quantidade == 1 else "linhas"
            print(f"✓ {nome:<30} {_formatar_quantidade(quantidade)} {unidade_linha}")
        quantidade_marts = len(resultados)
        unidade_mart = "mart" if quantidade_marts == 1 else "marts"
        unidade_linha = "linha" if total == 1 else "linhas"
        print(
            f"Total: {quantidade_marts} {unidade_mart}, "
            f"{_formatar_quantidade(total)} {unidade_linha}"
        )
    except MartsInvalidos as erro:
        print(erro)
        raise SystemExit(1) from erro
    finally:
        con.close()


if __name__ == "__main__":
    main()
