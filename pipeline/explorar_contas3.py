"""Abre os arquivos de prestação de contas e os processuais do TSE.

Conferir antes de usar: tamanho do arquivo, colunas, se há CPF (identificador
forte) e o que cada registro traz. CPFs aparecem mascarados.

Rodar:  python pipeline/explorar_contas3.py
"""

import collections
import json
import re
import urllib.request
import zipfile
from pathlib import Path

import tse

ODS = "https://cdn.tse.jus.br/estatistica/sead/odsele"
ALVOS = [
    f"{ODS}/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2026.zip",
    f"{ODS}/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2022.zip",
    f"{ODS}/processual/processo_eleitoral_2026.zip",
    f"{ODS}/processual/processos_eleitorais_partes_2026.zip",
    f"{ODS}/processual/processos_eleitorais_assuntos_2026.zip",
    f"{ODS}/processual/processos_eleitorais_decisoes_2026.zip",
    f"{ODS}/processual/processos_eleitorais_partes_2022.zip",
    f"{ODS}/processual/processos_eleitorais_assuntos_2022.zip",
]
LIMITE_MB = 900
MASCARA = re.compile(r"\b\d{11}\b")


def mascarar(valor) -> str:
    return MASCARA.sub(lambda m: m.group()[:3] + "********", str(valor))


def tamanho(url: str) -> float | None:
    pedido = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "alumia-aqui"})
    try:
        with urllib.request.urlopen(pedido, timeout=60) as resposta:
            return int(resposta.headers.get("Content-Length", 0)) / 1e6
    except Exception as erro:
        print(f"  HEAD falhou: {erro}")
        return None


def linhas_do_csv(z: zipfile.ZipFile, nome: str, maximo: int = 200_000):
    with z.open(nome) as arquivo:
        bruto = arquivo.read()
    texto = bruto.decode("latin-1")
    linhas = texto.splitlines()
    colunas = linhas[0].replace('"', "").split(";")
    for linha in linhas[1 : maximo + 1]:
        yield dict(zip(colunas, linha.replace('"', "").split(";")))


def ver(url: str) -> None:
    print(f"\n{'=' * 70}\n{Path(url).name}\n{'=' * 70}")
    mb = tamanho(url)
    print(f"  tamanho: {mb:.1f} MB" if mb else "  tamanho desconhecido")
    if mb and mb > LIMITE_MB:
        print("  grande demais para esta conferência")
        return
    destino = tse.PASTA_DADOS / Path(url).name
    try:
        tse.baixar_url(url, destino)
    except tse.ArquivoInexistente:
        print("  não publicado")
        return
    except Exception as erro:
        print(f"  falhou: {erro}")
        return

    with zipfile.ZipFile(destino) as z:
        csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
        print(f"  {len(csvs)} CSVs")
        prefixos: dict[str, list[str]] = collections.defaultdict(list)
        for nome in csvs:
            base = re.sub(r"_[A-Z]{2}\.csv$|\.csv$", "", Path(nome).name)
            prefixos[re.sub(r"_\d{4}$", "", base)].append(nome)

        for prefixo, nomes in prefixos.items():
            nome = sorted(nomes, key=lambda n: z.getinfo(n).file_size)[len(nomes) // 2]
            registros = list(linhas_do_csv(z, nome, 60_000))
            if not registros:
                print(f"\n  -- {prefixo}: vazio")
                continue
            colunas = list(registros[0])
            print(f"\n  -- {prefixo}  ({len(nomes)} arquivos; amostra: {Path(nome).name}, {len(registros)} linhas lidas)")
            print(f"     colunas ({len(colunas)}): {colunas}")
            primeiro = {
                k: mascarar(v) for k, v in registros[0].items()
                if re.search(r"CPF|CNPJ|NM_|SQ_|DS_|VR_|ST_|CD_CARGO|SG_UF|NR_|DT_|TP_", k, re.I)
            }
            print(f"     exemplo: {json.dumps(primeiro, ensure_ascii=False)[:1300]}")

            # Colunas com CPF de 11 dígitos: o que permite ligar à pessoa.
            for coluna in colunas:
                if "CPF" in coluna.upper():
                    valores = [r[coluna] for r in registros if re.fullmatch(r"\d{11}", (r[coluna] or "").strip())]
                    print(f"     {coluna}: {len(valores)} de {len(registros)} linhas com 11 dígitos")

            # Distribuição de colunas curtas e informativas.
            for coluna in colunas:
                if re.search(r"DS_(SITUACAO|JULGAMENTO|TIPO|CLASSE|ASSUNTO|DECISAO|ORIGEM|PARTE|CARGO)|NM_CLASSE|NM_ASSUNTO", coluna, re.I):
                    contagem = collections.Counter((r[coluna] or "").strip() for r in registros)
                    print(f"     {coluna}: {contagem.most_common(8)}")


if __name__ == "__main__":
    for url in ALVOS:
        ver(url)
