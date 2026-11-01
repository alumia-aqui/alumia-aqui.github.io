"""Junta aos Retratos as contas de campanha da eleição atual, publicadas pelo TSE.

Para cada candidatura:
- Receitas: total, divisão por origem (recursos próprios, de partido, de pessoas
  físicas...) e quanto veio de fundo público (Fundo Eleitoral e Fundo Partidário).
- Despesas: total contratado, total pago e divisão por tipo de gasto.
- Prestação: se o que está publicado é relatório parcial ou a prestação final,
  com a data.

Ligação com a pessoa: SQ_CANDIDATO, o código que o TSE dá ao registro da
candidatura. É o mesmo código que já está em cada candidatura do Retrato, então
não depende de nome nem de CPF. O TSE deixou de publicar o CPF do candidato
nesses arquivos.

Rodar depois de gerar_pessoas.py:  python pipeline/gerar_contas.py
"""

import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import tse
from gerar_pessoas import PASTA_SAIDA

URL = ("https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/"
       "prestacao_de_contas_eleitorais_candidatos_{ano}.zip")
FONTE = "https://dadosabertos.tse.jus.br/dataset/prestacao-de-contas-eleitorais-{ano}"
# Fontes que são dinheiro público, pelo nome que o TSE usa.
FUNDOS = {
    "Fundo Especial de Financiamento de Campanha": "Fundo Eleitoral",
    "Fundo Partidário": "Fundo Partidário",
}
CATEGORIAS = 6  # categorias mostradas antes de juntar o resto em "Outros"


def ler(caminho: Path, prefixo: str, ano: int):
    """Linhas do arquivo nacional de um prefixo (receitas, despesas...), uma a uma."""
    csv.field_size_limit(10_000_000)
    with zipfile.ZipFile(caminho) as z:
        nome = f"{prefixo}_{ano}_BRASIL.csv"
        if nome not in z.namelist():
            print(f"  {nome} não está no arquivo do TSE")
            return
        with z.open(nome) as bruto:
            texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
            yield from csv.DictReader(texto, delimiter=";")


def como_data(texto: str) -> tuple:
    """'30/10/2026' -> (2026, 10, 30), para comparar datas sem biblioteca."""
    partes = (texto or "").split("/")
    return tuple(int(p) for p in reversed(partes)) if len(partes) == 3 and all(
        p.isdigit() for p in partes) else (0, 0, 0)


def novo() -> dict:
    return {
        "receitas": 0.0, "por_origem": defaultdict(float), "fundos": defaultdict(float),
        "contratadas": 0.0, "pagas": 0.0, "por_tipo": defaultdict(float),
        "prestacao": None, "geracao": None,
    }


def maior_prestacao(atual, tipo: str | None, data: str | None):
    """Entre relatórios parciais e a prestação final, vale a mais recente; a final tem prioridade."""
    if not tipo or not data:
        return atual
    novo_valor = {"tipo": tipo.strip(), "data": data.strip()}
    if atual is None:
        return novo_valor
    final = lambda p: p["tipo"].lower().startswith("final")
    if final(novo_valor) != final(atual):
        return novo_valor if final(novo_valor) else atual
    return novo_valor if como_data(novo_valor["data"]) > como_data(atual["data"]) else atual


def arrumar(nome: str | None) -> str:
    nome = (tse.limpar(nome) or "Não informado").strip()
    return nome[0].upper() + nome[1:] if nome else "Não informado"


def principais(valores: dict[str, float]) -> list[dict]:
    """As maiores categorias; o resto vira uma linha de 'Outros'."""
    ordenadas = sorted(valores.items(), key=lambda i: i[1], reverse=True)
    saida = [{"nome": nome, "valor": round(valor, 2)} for nome, valor in ordenadas[:CATEGORIAS] if valor > 0]
    resto = sum(valor for _, valor in ordenadas[CATEGORIAS:])
    if resto > 0:
        saida.append({"nome": "Outros", "valor": round(resto, 2)})
    return saida


def coletar(caminho: Path, ano: int) -> dict[str, dict]:
    contas: dict[str, dict] = defaultdict(novo)
    prestador_para_candidato: dict[str, str] = {}

    for linha in ler(caminho, "receitas_candidatos", ano):
        sq = tse.limpar(linha.get("SQ_CANDIDATO"))
        valor = tse.valor_em_reais(linha.get("VR_RECEITA"))
        if not sq or valor is None:
            continue
        conta = contas[sq]
        conta["receitas"] += valor
        conta["por_origem"][arrumar(linha.get("DS_ORIGEM_RECEITA"))] += valor
        fundo = FUNDOS.get((tse.limpar(linha.get("DS_FONTE_RECEITA")) or "").strip())
        if fundo:
            conta["fundos"][fundo] += valor
        conta["prestacao"] = maior_prestacao(
            conta["prestacao"], linha.get("TP_PRESTACAO_CONTAS"), linha.get("DT_PRESTACAO_CONTAS"))
        conta["geracao"] = conta["geracao"] or tse.limpar(linha.get("DT_GERACAO"))
        prestador = tse.limpar(linha.get("SQ_PRESTADOR_CONTAS"))
        if prestador:
            prestador_para_candidato[prestador] = sq
    print(f"  receitas: {len(contas)} candidaturas")

    for linha in ler(caminho, "despesas_contratadas_candidatos", ano):
        sq = tse.limpar(linha.get("SQ_CANDIDATO"))
        valor = tse.valor_em_reais(linha.get("VR_DESPESA_CONTRATADA"))
        if not sq or valor is None:
            continue
        conta = contas[sq]
        conta["contratadas"] += valor
        conta["por_tipo"][arrumar(linha.get("DS_ORIGEM_DESPESA"))] += valor
        conta["prestacao"] = maior_prestacao(
            conta["prestacao"], linha.get("TP_PRESTACAO_CONTAS"), linha.get("DT_PRESTACAO_CONTAS"))
        conta["geracao"] = conta["geracao"] or tse.limpar(linha.get("DT_GERACAO"))
        prestador = tse.limpar(linha.get("SQ_PRESTADOR_CONTAS"))
        if prestador:
            prestador_para_candidato[prestador] = sq

    # As despesas pagas só trazem o código do prestador de contas.
    sem_dono = 0
    for linha in ler(caminho, "despesas_pagas_candidatos", ano):
        prestador = tse.limpar(linha.get("SQ_PRESTADOR_CONTAS"))
        sq = prestador_para_candidato.get(prestador or "")
        valor = tse.valor_em_reais(linha.get("VR_PAGTO_DESPESA"))
        if valor is None:
            continue
        if not sq:
            sem_dono += 1
            continue
        contas[sq]["pagas"] += valor
    print(f"  despesas: {len(contas)} candidaturas ({sem_dono} pagamentos sem candidatura correspondente)")
    return contas


def finalizar(conta: dict, ano: int) -> dict:
    return {
        "ano": ano,
        "atualizado_em": conta["geracao"],
        "prestacao": conta["prestacao"],
        "receitas": {
            "total": round(conta["receitas"], 2),
            "por_origem": principais(conta["por_origem"]),
            "fundos": principais(conta["fundos"]),
        },
        "despesas": {
            "contratadas": round(conta["contratadas"], 2),
            "pagas": round(conta["pagas"], 2),
            "por_tipo": principais(conta["por_tipo"]),
        },
        "fonte": FONTE.format(ano=ano),
    }


def main() -> None:
    pasta_pessoas = PASTA_SAIDA / "pessoas"
    arquivos = sorted(pasta_pessoas.glob("*.json"))
    if not arquivos:
        raise SystemExit("Nenhuma pessoa em pipeline/saida. Rode antes: python pipeline/gerar_pessoas.py")
    pessoas = [json.loads(f.read_text(encoding="utf-8")) for f in arquivos]
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else max(
        c["ano"] for p in pessoas for c in p["candidaturas"])
    print(f"Contas de campanha de {ano}")

    caminho = tse.baixar_url(URL.format(ano=ano), tse.PASTA_DADOS / f"contas_candidatos_{ano}.zip")
    contas = coletar(caminho, ano)

    com_contas = 0
    for pessoa, arquivo in zip(pessoas, arquivos):
        # Uma pessoa pode ter mais de um registro na mesma eleição; cada um tem contas próprias.
        registros = [c for c in pessoa["candidaturas"] if c["ano"] == ano and c.get("sq_candidato") in contas]
        if registros:
            escolhida = max(registros, key=lambda c: contas[c["sq_candidato"]]["receitas"])
            pessoa["campanha"] = finalizar(contas[escolhida["sq_candidato"]], ano)
            com_contas += 1
        else:
            pessoa.pop("campanha", None)
        arquivo.write_text(json.dumps(pessoa, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{com_contas} de {len(pessoas)} pessoas com contas de campanha publicadas")


if __name__ == "__main__":
    main()
