"""Leitura dos arquivos de candidatos do TSE (consulta_cand).

Funções compartilhadas pelos scripts do pipeline: download do zip de um ano
e leitura das linhas dos CSVs, uma por vez, para não carregar tudo na memória.
"""

import csv
import io
import urllib.request
import zipfile
from collections.abc import Iterator
from pathlib import Path

URL_CANDIDATOS = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{ano}.zip"
PASTA_DADOS = Path(__file__).parent / "dados_brutos"

# Valores que o TSE usa para "sem informação".
VALORES_NULOS = {"", "#NULO#", "#NULO", "#NE", "#NE#", "-1", "-3", "-4"}


def limpar(valor: str | None) -> str | None:
    if valor is None:
        return None
    valor = valor.strip()
    return None if valor in VALORES_NULOS else valor


def baixar_candidatos(ano: int) -> Path:
    PASTA_DADOS.mkdir(exist_ok=True)
    destino = PASTA_DADOS / f"consulta_cand_{ano}.zip"
    if destino.exists():
        return destino

    url = URL_CANDIDATOS.format(ano=ano)
    print(f"Baixando {url}")
    temporario = destino.with_suffix(".parcial")
    with urllib.request.urlopen(url) as resposta, open(temporario, "wb") as arquivo:
        total = int(resposta.headers.get("Content-Length", 0))
        baixado = 0
        while bloco := resposta.read(1024 * 1024):
            arquivo.write(bloco)
            baixado += len(bloco)
            if total:
                print(f"\r  {baixado / total:.0%} de {total / 1e6:.1f} MB", end="")
    print()
    temporario.rename(destino)  # só vira arquivo final se o download terminou
    return destino


def ler_candidatos(ano: int) -> Iterator[dict]:
    """Devolve as linhas de candidatos de um ano, uma a uma."""
    caminho = baixar_candidatos(ano)
    csv.field_size_limit(10_000_000)
    with zipfile.ZipFile(caminho) as z:
        csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
        # O arquivo _BRASIL junta todos os estados. Sem ele, lê estado por estado.
        brasil = [n for n in csvs if n.upper().endswith("_BRASIL.CSV")]
        for nome in brasil or csvs:
            with z.open(nome) as bruto:
                texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
                yield from csv.DictReader(texto, delimiter=";")
