"""Exploração dos dados abertos da Câmara e do Senado.

Mostra colunas e exemplos de cada fonte da Fase 2, para decidir como ligar
parlamentares às pessoas do TSE. Números com formato de CPF são mascarados,
porque a saída pode aparecer em logs públicos.

Uso:  python pipeline/explorar_parlamento.py
"""

import csv
import io
import json
import re
import urllib.request
import zipfile

CABECALHO = {"User-Agent": "alumia-aqui (dados abertos)", "Accept": "application/json"}


def baixar(url: str, limite: int | None = None) -> bytes:
    pedido = urllib.request.Request(url, headers=CABECALHO)
    with urllib.request.urlopen(pedido, timeout=120) as resposta:
        return resposta.read(limite) if limite else resposta.read()


def mascarar(texto: str) -> str:
    return re.sub(r"\d{11}", lambda m: m.group(0)[:3] + "********", texto)


def mostrar_csv(titulo: str, url: str, separador: str = ";", zipado: bool = False, linhas: int = 2) -> None:
    print(f"\n=== {titulo}\n{url}")
    try:
        dados = baixar(url)
    except Exception as erro:
        print(f"  ERRO: {erro}")
        return
    print(f"  tamanho: {len(dados) / 1e6:.1f} MB")
    if zipado:
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            nome = z.namelist()[0]
            print(f"  arquivos no zip: {z.namelist()}")
            dados = z.read(nome)
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            texto = dados.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    leitor = csv.DictReader(io.StringIO(texto), delimiter=separador)
    registros = list(leitor)
    print(f"  registros: {len(registros)}")
    print(f"  colunas: {leitor.fieldnames}")
    for registro in registros[:linhas]:
        print("  exemplo:", mascarar(json.dumps(registro, ensure_ascii=False))[:900])


def mostrar_json(titulo: str, url: str, caracteres: int = 1500) -> None:
    print(f"\n=== {titulo}\n{url}")
    try:
        dados = baixar(url)
    except Exception as erro:
        print(f"  ERRO: {erro}")
        return
    print("  ", mascarar(dados.decode("utf-8", "replace"))[:caracteres])


def main() -> None:
    camara = "https://dadosabertos.camara.leg.br"
    mostrar_csv("Câmara: deputados (todos os tempos)", f"{camara}/arquivos/deputados/csv/deputados.csv")
    mostrar_json("Câmara: deputados da legislatura 57 (API)", f"{camara}/api/v2/deputados?idLegislatura=57&itens=2")
    mostrar_json("Câmara: detalhe de um deputado (API)", f"{camara}/api/v2/deputados/204554")
    mostrar_csv("Câmara: autores de proposições 2025", f"{camara}/arquivos/proposicoesAutores/csv/proposicoesAutores-2025.csv")
    mostrar_csv("Câmara: proposições 2025", f"{camara}/arquivos/proposicoes/csv/proposicoes-2025.csv", linhas=1)
    mostrar_csv("Câmara: cota parlamentar 2025", "https://www.camara.leg.br/cotas/Ano-2025.csv.zip", zipado=True, linhas=1)

    senado = "https://legis.senado.leg.br/dadosabertos"
    mostrar_json("Senado: senadores da legislatura 57", f"{senado}/senador/lista/legislatura/57.json")
    mostrar_json("Senado: detalhe de um senador", f"{senado}/senador/5012.json")
    mostrar_json("Senado: autorias de um senador", f"{senado}/senador/5012/autorias.json")
    mostrar_csv(
        "Senado: cota parlamentar (CEAPS) 2025",
        "https://www.senado.leg.br/transparencia/LAI/verba/despesa_ceaps_2025.csv",
        linhas=1,
    )


if __name__ == "__main__":
    main()
