"""Exploração inicial dos dados de candidatos do TSE.

Baixa o arquivo consulta_cand de um ano de eleição e imprime um resumo:
arquivos dentro do zip, colunas, total de candidatos, distribuição por cargo
e preenchimento dos campos que podem servir para identificar a mesma pessoa
entre eleições.

Usa só a biblioteca padrão do Python. Não precisa instalar nada.

Uso:
    python pipeline/explorar_tse.py          (ano padrão: 2026)
    python pipeline/explorar_tse.py 2022
"""

import csv
import io
import sys
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

URL_BASE = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{ano}.zip"
PASTA_DADOS = Path(__file__).parent / "dados_brutos"

# Campos candidatos a identificador estável da pessoa.
CAMPOS_IDENTIFICADORES = [
    "SQ_CANDIDATO",
    "NR_CPF_CANDIDATO",
    "NR_TITULO_ELEITORAL_CANDIDATO",
    "DT_NASCIMENTO",
]


def baixar(ano: int) -> Path:
    PASTA_DADOS.mkdir(exist_ok=True)
    destino = PASTA_DADOS / f"consulta_cand_{ano}.zip"
    if destino.exists():
        print(f"Usando arquivo já baixado: {destino}")
        return destino

    url = URL_BASE.format(ano=ano)
    print(f"Baixando {url}")
    with urllib.request.urlopen(url) as resposta, open(destino, "wb") as arquivo:
        total = int(resposta.headers.get("Content-Length", 0))
        baixado = 0
        while bloco := resposta.read(1024 * 1024):
            arquivo.write(bloco)
            baixado += len(bloco)
            if total:
                print(f"\r  {baixado / total:.0%} de {total / 1e6:.1f} MB", end="")
    print()
    return destino


def mascarar(valor: str) -> str:
    """Mostra só o formato do valor (dígitos viram 9), para não imprimir dado pessoal."""
    return "".join("9" if c.isdigit() else c for c in valor)


def explorar(caminho_zip: Path) -> None:
    with zipfile.ZipFile(caminho_zip) as z:
        nomes = z.namelist()
        print(f"\nArquivos no zip ({len(nomes)}):")
        for nome in nomes:
            print(f"  {nome}")

        # O TSE costuma incluir um arquivo _BRASIL com todos os estados juntos.
        csvs = [n for n in nomes if n.lower().endswith(".csv")]
        brasil = [n for n in csvs if "BRASIL" in n.upper()]
        arquivos = brasil if brasil else csvs
        print(f"\nLendo: {', '.join(arquivos)}")

        csv.field_size_limit(10_000_000)
        linhas = []
        for nome in arquivos:
            with z.open(nome) as bruto:
                texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
                linhas.extend(csv.DictReader(texto, delimiter=";"))

    if not linhas:
        print("Nenhuma linha encontrada.")
        return

    colunas = list(linhas[0].keys())
    print(f"\nColunas ({len(colunas)}):")
    for coluna in colunas:
        print(f"  {coluna}")

    print(f"\nTotal de registros: {len(linhas)}")

    if "DS_CARGO" in colunas:
        print("\nCandidatos por cargo:")
        for cargo, qtd in Counter(l["DS_CARGO"] for l in linhas).most_common():
            print(f"  {cargo}: {qtd}")

    print("\nCampos identificadores (preenchimento e formato):")
    for campo in CAMPOS_IDENTIFICADORES:
        if campo not in colunas:
            print(f"  {campo}: coluna não existe")
            continue
        valores = [l[campo] for l in linhas]
        vazios = sum(1 for v in valores if v.strip() in ("", "#NULO#", "#NULO", "-1", "-4"))
        distintos = len(set(valores))
        formatos = Counter(mascarar(v) for v in valores).most_common(3)
        print(f"  {campo}: {len(valores) - vazios} preenchidos, {distintos} valores distintos")
        for formato, qtd in formatos:
            print(f"      formato '{formato}': {qtd}")


def main() -> None:
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    explorar(baixar(ano))


if __name__ == "__main__":
    main()
