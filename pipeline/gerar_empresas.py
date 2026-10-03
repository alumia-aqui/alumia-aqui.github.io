"""Encontra as empresas em que cada candidato é sócio (dados abertos do CNPJ, Receita Federal).

Roda no computador local, uma vez por mês: os servidores da Receita recusam
conexões vindas do GitHub. O resultado vai para dados/empresas.json, que entra
no repositório e é juntado aos Retratos na publicação (juntar_empresas.py).

Ligação: a Receita publica o CPF do sócio mascarado (***123456**). A ligação
exige os 6 dígitos do meio iguais e o nome completo idêntico ao do TSE.

Dados usados de cada empresa: razão social, natureza jurídica, capital social,
porte e, do estabelecimento matriz, situação cadastral, UF, município, data de
início e atividade principal. Endereço, telefone e e-mail ficam de fora: em
empresas pequenas costumam ser dados pessoais do dono.

O CNPJ é tratado como texto (há CNPJ alfanumérico desde 2026).

Uso:  python pipeline/gerar_empresas.py
Tamanho: os arquivos da Receita somam alguns GB por mês. Só o mês atual fica guardado.
"""

import csv
import io
import json
import re
import shutil
import sys
import unicodedata
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

import tse
from gerar_pessoas import carregar_chave, codigo_pessoa

BASES = [
    "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/",
    "https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/",
]
PASTA = tse.PASTA_DADOS / "receita"
SAIDA = Path(__file__).parent.parent / "dados" / "empresas.json"

SITUACOES = {"01": "Nula", "1": "Nula", "02": "Ativa", "2": "Ativa", "03": "Suspensa", "3": "Suspensa",
             "04": "Inapta", "4": "Inapta", "08": "Baixada", "8": "Baixada"}
PORTES = {"00": "Não informado", "01": "Microempresa", "03": "Empresa de pequeno porte", "05": "Demais"}


def normalizar(texto: str | None) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^A-Za-z ]", " ", texto).upper().split())


def pagina(url: str) -> str:
    pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (alumia-aqui; dados abertos)"})
    with urllib.request.urlopen(pedido, timeout=120) as resposta:
        return resposta.read().decode("utf-8", "replace")


def localizar_mes() -> tuple[str, str, list[str]]:
    """Endereço da pasta do mês mais recente e os arquivos .zip dela."""
    for base in BASES:
        try:
            meses = sorted(set(re.findall(r'href="(\d{4}-\d{2})/?"', pagina(base))))
        except Exception as erro:
            print(f"  {base}: {erro}")
            continue
        if meses:
            pasta = f"{base}{meses[-1]}/"
            arquivos = sorted(set(re.findall(r'href="([^"/]+\.zip)"', pagina(pasta))))
            return meses[-1], pasta, arquivos
    sys.exit(
        "Não encontrei os arquivos da Receita. O endereço pode ter mudado: confira em "
        "https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj"
    )


def baixar(url: str, destino: Path) -> Path:
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    return tse.baixar_url(url, destino)


def linhas(caminho: Path):
    """Arquivos da Receita: CSV sem cabeçalho, separado por ';', em latin-1."""
    csv.field_size_limit(10_000_000)
    with zipfile.ZipFile(caminho) as z:
        for nome in z.namelist():
            with z.open(nome) as bruto:
                yield from csv.reader(io.TextIOWrapper(bruto, encoding="latin-1", newline=""), delimiter=";")


def tabela(caminho: Path) -> dict[str, str]:
    """Tabelas auxiliares (código;descrição)."""
    return {l[0].strip(): l[1].strip() for l in linhas(caminho) if len(l) >= 2}


def main() -> None:
    chave = carregar_chave()

    # Candidatos da eleição atual: (6 dígitos do meio do CPF, nome) -> código da pessoa.
    anos = sorted(int(m.group(1)) for f in tse.PASTA_DADOS.glob("consulta_cand_*.zip")
                  if (m := re.search(r"_(\d{4})\.zip$", f.name)))
    ano = anos[-1] if anos else date.today().year
    candidatos: dict[tuple[str, str], str] = {}
    for linha in tse.ler_candidatos(ano):
        cpf = tse.limpar(linha.get("NR_CPF_CANDIDATO"))
        if cpf and cpf.isdigit() and len(cpf) == 11:
            candidatos[(cpf[3:9], normalizar(linha.get("NM_CANDIDATO")))] = codigo_pessoa(cpf, chave)
    print(f"Candidatos de {ano}: {len(candidatos)}")

    mes, pasta, arquivos = localizar_mes()
    print(f"Receita Federal: arquivos de {mes}")
    destino_mes = PASTA / mes
    for antigo in PASTA.glob("*"):  # só o mês atual fica guardado
        if antigo.is_dir() and antigo != destino_mes:
            shutil.rmtree(antigo)

    def baixar_grupo(prefixo: str) -> list[Path]:
        return [baixar(pasta + a, destino_mes / a) for a in arquivos if a.lower().startswith(prefixo.lower())]

    # 1. Sócios pessoa física que são candidatos.
    socios: dict[str, list[dict]] = {}  # cnpj_basico -> vínculos
    for caminho in baixar_grupo("Socios"):
        for l in linhas(caminho):
            if len(l) < 6 or l[1] != "2":  # 2 = pessoa física
                continue
            digitos = re.sub(r"\D", "", l[3])
            if len(digitos) != 6:
                continue
            id_pessoa = candidatos.get((digitos, normalizar(l[2])))
            if id_pessoa:
                socios.setdefault(l[0], []).append(
                    {"pessoa": id_pessoa, "qualificacao": l[4].strip(), "entrada": l[5].strip()}
                )
    print(f"  {sum(len(v) for v in socios.values())} vínculos de sócio encontrados, em {len(socios)} empresas")

    # 2. Dados da empresa.
    empresas: dict[str, dict] = {}
    for caminho in baixar_grupo("Empresas"):
        for l in linhas(caminho):
            if len(l) >= 6 and l[0] in socios:
                empresas[l[0]] = {
                    "razao_social": l[1].strip(), "natureza": l[2].strip(),
                    "capital_social": tse.valor_em_reais(l[4]), "porte": PORTES.get(l[5].strip()),
                }

    # 3. Estabelecimento matriz: situação, local, início e atividade (sem endereço nem contatos).
    for caminho in baixar_grupo("Estabelecimentos"):
        for l in linhas(caminho):
            if len(l) >= 21 and l[0] in empresas and l[3] == "1":
                empresas[l[0]].update({
                    "cnpj": f"{l[0]}{l[1]}{l[2]}", "nome_fantasia": l[4].strip() or None,
                    "situacao": SITUACOES.get(l[5].strip(), l[5].strip()), "data_situacao": l[6].strip(),
                    "inicio": l[10].strip(), "cnae": l[11].strip(), "uf": l[19].strip(), "municipio": l[20].strip(),
                })

    # 4. Tabelas de códigos.
    nomes = {}
    for prefixo in ("Qualificacoes", "Naturezas", "Municipios", "Cnaes"):
        caminhos = baixar_grupo(prefixo)
        nomes[prefixo] = tabela(caminhos[0]) if caminhos else {}

    def data(texto: str | None) -> str | None:
        return f"{texto[:4]}-{texto[4:6]}-{texto[6:8]}" if texto and len(texto) == 8 and texto.isdigit() and texto != "00000000" else None

    por_pessoa: dict[str, list[dict]] = {}
    for basico, vinculos in socios.items():
        e = empresas.get(basico, {})
        for v in vinculos:
            por_pessoa.setdefault(v["pessoa"], []).append({
                "cnpj_basico": basico,
                "cnpj": e.get("cnpj"),
                "razao_social": e.get("razao_social"),
                "nome_fantasia": e.get("nome_fantasia"),
                "qualificacao": nomes["Qualificacoes"].get(v["qualificacao"], v["qualificacao"]),
                "entrada": data(v["entrada"]),
                "natureza": nomes["Naturezas"].get(e.get("natureza"), e.get("natureza")),
                "capital_social": e.get("capital_social"),
                "porte": e.get("porte"),
                "situacao": e.get("situacao"),
                "data_situacao": data(e.get("data_situacao")),
                "inicio_atividade": data(e.get("inicio")),
                "atividade": nomes["Cnaes"].get(e.get("cnae"), e.get("cnae")),
                "uf": e.get("uf"),
                "municipio": nomes["Municipios"].get(e.get("municipio"), e.get("municipio")),
            })

    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text(json.dumps({
        "referencia": mes,
        "gerado_em": date.today().isoformat(),
        "pessoas": {p: sorted(v, key=lambda e: e["entrada"] or "", reverse=True) for p, v in sorted(por_pessoa.items())},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {len(por_pessoa)} candidatos sócios de empresas. Resultado em {SAIDA}")


if __name__ == "__main__":
    main()
