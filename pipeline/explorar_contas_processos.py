"""Verifica o que existe nas fontes do TSE sobre contas de campanha e processos.

Nada entra no site a partir daqui. O script só mostra quais arquivos existem,
quais colunas trazem e se há identificador forte (CPF) para ligar à pessoa.
CPFs aparecem mascarados.

Rodar:  python pipeline/explorar_contas_processos.py
"""

import json
import re
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import tse

ANOS = (2026, 2022)
CONJUNTOS = (
    "prestacao_de_contas_eleitorais_candidatos",
    "prestacao_de_contas_eleitorais_partidos",
    "motivo_cassacao",
)
DIVULGA = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1"
MASCARA = re.compile(r"\b\d{11}\b")


def mascarar(valor) -> str:
    return MASCARA.sub(lambda m: m.group()[:3] + "********", str(valor))


def cabecalho(titulo: str) -> None:
    print(f"\n{'=' * 70}\n{titulo}\n{'=' * 70}")


def ver_zip(conjunto: str, ano: int) -> None:
    cabecalho(f"{conjunto} {ano}")
    try:
        caminho = tse.baixar(conjunto, ano)
    except tse.ArquivoInexistente:
        print("  não publicado")
        return
    except Exception as erro:
        print(f"  falhou: {erro}")
        return
    with zipfile.ZipFile(caminho) as z:
        nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
        print(f"  {len(nomes)} arquivos CSV. Exemplos: {nomes[:6]}")
        # Um arquivo por prefixo (receitas, despesas, doador originário...).
        prefixos: dict[str, str] = {}
        for nome in nomes:
            prefixo = re.sub(r"_[A-Z]{2}\.csv$|\.csv$", "", Path(nome).name)
            prefixo = re.sub(r"_\d{4}$", "", prefixo)
            prefixos.setdefault(prefixo, nome)
        for prefixo, nome in prefixos.items():
            with z.open(nome) as arquivo:
                texto = arquivo.read(400_000).decode("latin-1")
            linhas = texto.splitlines()
            if not linhas:
                print(f"  {prefixo}: vazio")
                continue
            colunas = linhas[0].replace('"', "").split(";")
            print(f"\n  -- {prefixo} ({nome})")
            print(f"     colunas ({len(colunas)}): {colunas}")
            if len(linhas) > 1:
                valores = linhas[1].replace('"', "").split(";")
                amostra = dict(zip(colunas, valores))
                interessantes = {
                    k: mascarar(v) for k, v in amostra.items()
                    if re.search(r"CPF|CNPJ|NOME|SQ_|CARGO|UF|VALOR|RECEITA|DESPESA|JULGAMENTO|PARECER|SITUACAO|MOTIVO|DATA", k, re.I)
                }
                print(f"     exemplo: {json.dumps(interessantes, ensure_ascii=False)[:1200]}")


def pedir(url: str, limite: int = 900) -> dict | None:
    try:
        pedido = urllib.request.Request(url, headers={"User-Agent": "alumia-aqui (dados abertos)"})
        with urllib.request.urlopen(pedido, timeout=60) as resposta:
            dados = resposta.read()
        print(f"  {resposta.status} {url}")
    except urllib.error.HTTPError as erro:
        print(f"  {erro.code} {url}")
        return None
    except Exception as erro:
        print(f"  erro {erro} {url}")
        return None
    try:
        conteudo = json.loads(dados)
    except ValueError:
        print(f"     (não é JSON) {mascarar(dados[:200])}")
        return None
    print(f"     {mascarar(json.dumps(conteudo, ensure_ascii=False))[:limite]}")
    return conteudo


def ver_divulga() -> None:
    cabecalho("DivulgaCandContas: estrutura por candidato")
    # Um candidato real de 2026, tirado do próprio arquivo do TSE.
    exemplo = None
    for linha in tse.ler_candidatos(2026):
        if tse.limpar(linha.get("DS_CARGO")) == "DEPUTADO FEDERAL":
            exemplo = linha
            break
    if not exemplo:
        print("  nenhum candidato de 2026 no arquivo")
        return
    sq = tse.limpar(exemplo.get("SQ_CANDIDATO"))
    ue = tse.limpar(exemplo.get("SG_UE"))
    eleicao = tse.limpar(exemplo.get("CD_ELEICAO"))
    print(f"  candidato de teste: {tse.limpar(exemplo.get('NM_URNA_CANDIDATO'))}, "
          f"UE {ue}, eleição {eleicao}, SQ {sq}")

    detalhe = pedir(f"{DIVULGA}/candidatura/buscar/2026/{ue}/{eleicao}/candidato/{sq}", limite=2500)
    if isinstance(detalhe, dict):
        print(f"\n     chaves do candidato: {sorted(detalhe.keys())}")
        for chave in detalhe:
            if re.search(r"process|certid|crime|julg|conta|sancao|substit", chave, re.I):
                print(f"     >> {chave}: {mascarar(json.dumps(detalhe[chave], ensure_ascii=False))[:1500]}")

    print("\n  Outros caminhos da mesma API:")
    for caminho in (
        f"/processo/listar/2026/{ue}/{eleicao}/{sq}",
        f"/candidatura/processos/2026/{ue}/{eleicao}/{sq}",
        f"/prestador/consultar/2026/{ue}/{eleicao}/{sq}",
        f"/prestador/buscar/2026/{ue}/{eleicao}/candidato/{sq}",
    ):
        pedir(DIVULGA + caminho, limite=700)


def ver_consulta_cand() -> None:
    cabecalho("consulta_cand 2026: colunas sobre julgamento e resultado")
    primeira = next(tse.ler_candidatos(2026))
    colunas = [c for c in primeira if re.search(r"SITUACAO|JULG|TOT_TURNO|MOTIVO|CASSA|DETALHE|PROTOCOLO|PROCESSO", c, re.I)]
    print(f"  {colunas}")
    print(f"  exemplo: {json.dumps({c: tse.limpar(primeira.get(c)) for c in colunas}, ensure_ascii=False)}")


if __name__ == "__main__":
    ver_consulta_cand()
    for ano in ANOS:
        for conjunto in CONJUNTOS:
            ver_zip(conjunto, ano)
    ver_divulga()
