"""Leitura dos arquivos de dados abertos do TSE.

Funções compartilhadas pelos scripts do pipeline: download do zip de um
conjunto de dados (candidatos, bens) para um ano e leitura das linhas dos
CSVs, uma por vez, para não carregar tudo na memória.
"""

import csv
import io
import urllib.error
import urllib.request
import zipfile
from collections.abc import Iterator
from pathlib import Path

URL_CONJUNTO = "https://cdn.tse.jus.br/estatistica/sead/odsele/{conjunto}/{conjunto}_{ano}.zip"
PASTA_DADOS = Path(__file__).parent / "dados_brutos"

# Valores que o TSE usa para "sem informação".
VALORES_NULOS = {"", "#NULO#", "#NULO", "#NE", "#NE#", "-1", "-3", "-4"}


class ArquivoInexistente(Exception):
    """O TSE não publicou esse conjunto para esse ano."""


def limpar(valor: str | None) -> str | None:
    if valor is None:
        return None
    valor = valor.strip()
    return None if valor in VALORES_NULOS else valor


def valor_em_reais(texto: str | None) -> float | None:
    """'150000,00' ou '150000.00' -> 150000.0"""
    texto = limpar(texto)
    if not texto:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def baixar_url(url: str, destino: Path) -> Path:
    """Baixa url para destino, mostrando o progresso. Não baixa de novo se já existe."""
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    print(f"Baixando {url}")
    temporario = destino.with_suffix(".parcial")
    try:
        resposta = urllib.request.urlopen(url)
    except urllib.error.HTTPError as erro:
        if erro.code in (403, 404):
            raise ArquivoInexistente(url) from erro
        raise
    with resposta, open(temporario, "wb") as arquivo:
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


def baixar(conjunto: str, ano: int) -> Path:
    url = URL_CONJUNTO.format(conjunto=conjunto, ano=ano)
    return baixar_url(url, PASTA_DADOS / f"{conjunto}_{ano}.zip")


def ler(conjunto: str, ano: int) -> Iterator[dict]:
    """Devolve as linhas de um conjunto de dados de um ano, uma a uma."""
    caminho = baixar(conjunto, ano)
    csv.field_size_limit(10_000_000)
    with zipfile.ZipFile(caminho) as z:
        csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
        # O arquivo _BRASIL junta todos os estados. Sem ele, lê estado por estado.
        brasil = [n for n in csvs if n.upper().endswith("_BRASIL.CSV")]
        for nome in brasil or csvs:
            with z.open(nome) as bruto:
                texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
                yield from csv.DictReader(texto, delimiter=";")


def ler_candidatos(ano: int) -> Iterator[dict]:
    return ler("consulta_cand", ano)


def ler_bens(ano: int) -> Iterator[dict]:
    return ler("bem_candidato", ano)
