"""Procura no catálogo de dados abertos do TSE os arquivos de prestação de contas.

O endereço padrão de tse.py não serve para esse conjunto. Aqui o catálogo
(CKAN) é consultado para descobrir o endereço real de cada arquivo.

Rodar:  python pipeline/explorar_contas2.py
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import tse

CKAN = "https://dadosabertos.tse.jus.br/api/3/action"
BUSCAS = ("prestação de contas", "certidão", "processo")
MASCARA = re.compile(r"\b\d{11}\b")


def mascarar(valor) -> str:
    return MASCARA.sub(lambda m: m.group()[:3] + "********", str(valor))


def pedir(url: str):
    pedido = urllib.request.Request(url, headers={"User-Agent": "alumia-aqui (dados abertos)"})
    with urllib.request.urlopen(pedido, timeout=120) as resposta:
        return json.loads(resposta.read())


def cabecalho(titulo: str) -> None:
    print(f"\n{'=' * 70}\n{titulo}\n{'=' * 70}")


def buscar(termo: str) -> list[dict]:
    cabecalho(f"Catálogo: {termo}")
    url = f"{CKAN}/package_search?q={urllib.parse.quote(termo)}&rows=30"
    try:
        resposta = pedir(url)
    except Exception as erro:
        print(f"  falhou: {erro}")
        return []
    pacotes = resposta["result"]["results"]
    print(f"  {resposta['result']['count']} conjuntos; mostrando {len(pacotes)}")
    for pacote in pacotes:
        zips = [r for r in pacote.get("resources", []) if r.get("url", "").endswith(".zip")]
        print(f"\n  * {pacote['title']}  ({pacote['name']})")
        for recurso in zips[:4]:
            print(f"      {recurso.get('name')}: {recurso['url']}")
        if len(zips) > 4:
            print(f"      ... mais {len(zips) - 4} arquivos")
    return pacotes


def ver_zip(url: str) -> None:
    cabecalho(f"Conteúdo de {url}")
    destino = tse.PASTA_DADOS / Path(urllib.parse.urlparse(url).path).name
    try:
        tse.baixar_url(url, destino)
    except Exception as erro:
        print(f"  falhou: {erro}")
        return
    with zipfile.ZipFile(destino) as z:
        nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
        print(f"  {len(nomes)} CSVs. Exemplos: {nomes[:5]}")
        prefixos: dict[str, str] = {}
        for nome in nomes:
            prefixo = re.sub(r"_[A-Z]{2}\.csv$|\.csv$", "", Path(nome).name)
            prefixos.setdefault(re.sub(r"_\d{4}$", "", prefixo), nome)
        for prefixo, nome in prefixos.items():
            with z.open(nome) as arquivo:
                texto = arquivo.read(300_000).decode("latin-1")
            linhas = texto.splitlines()
            colunas = linhas[0].replace('"', "").split(";") if linhas else []
            print(f"\n  -- {prefixo}")
            print(f"     colunas ({len(colunas)}): {colunas}")
            if len(linhas) > 1:
                amostra = dict(zip(colunas, linhas[1].replace('"', "").split(";")))
                guardar = {
                    k: mascarar(v) for k, v in amostra.items()
                    if re.search(r"CPF|CNPJ|NM_|SQ_|CARGO|UF|VR_|DS_|ST_|NR_PARTIDO", k, re.I)
                }
                print(f"     exemplo: {json.dumps(guardar, ensure_ascii=False)[:1400]}")


if __name__ == "__main__":
    encontrados = []
    for termo in BUSCAS:
        for pacote in buscar(termo):
            for recurso in pacote.get("resources", []):
                url = recurso.get("url", "")
                if url.endswith(".zip") and re.search(r"(2026|2022)", url):
                    encontrados.append(url)

    cabecalho("Arquivos de 2026 e 2022 encontrados")
    for url in sorted(set(encontrados)):
        print(f"  {url}")

    # Abre um de cada ano, se houver.
    for ano in ("2026", "2022"):
        alvo = next((u for u in sorted(set(encontrados)) if ano in u and "contas" in u.lower()), None)
        if alvo:
            ver_zip(alvo)
