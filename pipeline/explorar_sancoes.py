"""Exploração das fontes da Fase 3: sanções (CGU, TCU) e sócios de empresas (Receita).

Mostra formato, colunas e exemplos. Números com cara de CPF são mascarados,
porque a saída pode aparecer em logs públicos.

Uso:  python pipeline/explorar_sancoes.py
"""

import csv
import io
import json
import re
import urllib.request
import zipfile
from datetime import date, timedelta

CABECALHO = {"User-Agent": "Mozilla/5.0 (alumia-aqui; dados abertos)", "Accept": "*/*"}


def baixar(url: str, limite: int | None = None) -> bytes:
    pedido = urllib.request.Request(url, headers=CABECALHO)
    with urllib.request.urlopen(pedido, timeout=300) as resposta:
        return resposta.read(limite) if limite else resposta.read()


def mascarar(texto: str) -> str:
    texto = re.sub(r"\d{3}\.\d{3}\.\d{3}-\d{2}", "***.***.***-**", texto)
    return re.sub(r"(?<!\d)\d{11}(?!\d)", "***********", texto)


def mostrar_zip_csv(titulo: str, dados: bytes, linhas: int = 2) -> None:
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        print(f"  arquivos: {[(n, z.getinfo(n).file_size) for n in z.namelist()]}")
        nome = z.namelist()[0]
        bruto = z.read(nome)
    texto = None
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            texto = bruto.decode(codificacao)
            break
        except UnicodeDecodeError:
            pass
    separador = ";" if texto[:2000].count(";") > texto[:2000].count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto), delimiter=separador)
    registros = list(leitor)
    print(f"  {titulo}: {len(registros)} registros")
    print(f"  colunas: {leitor.fieldnames}")
    for r in registros[:linhas]:
        print("  exemplo:", mascarar(json.dumps(r, ensure_ascii=False))[:1200])
    # Como o CPF aparece (formato, sem os dígitos).
    for coluna in leitor.fieldnames or []:
        if "CPF" in coluna.upper():
            formatos = {}
            for r in registros[:5000]:
                f = re.sub(r"\d", "9", r.get(coluna) or "")
                formatos[f] = formatos.get(f, 0) + 1
            print(f"  formatos da coluna {coluna}: {sorted(formatos.items(), key=lambda i: -i[1])[:4]}")


def portal(cadastro: str) -> None:
    print(f"\n=== Portal da Transparência: {cadastro.upper()}")
    for dias in range(0, 10):
        dia = (date.today() - timedelta(days=dias)).strftime("%Y%m%d")
        url = f"https://portaldatransparencia.gov.br/download-de-dados/{cadastro}/{dia}"
        try:
            dados = baixar(url)
        except Exception as erro:
            print(f"  {dia}: {erro}")
            continue
        print(f"  {url}: {len(dados) / 1e6:.1f} MB, começa com {dados[:4]!r}")
        if dados[:2] == b"PK":
            mostrar_zip_csv(cadastro, dados)
            return


def tcu() -> None:
    print("\n=== TCU: consultas de condenações")
    for nome in ("inabilitados", "inidoneos", "irregulares", "contas-irregulares"):
        url = f"https://contas.tcu.gov.br/ords/condenacao/consulta/{nome}"
        try:
            dados = baixar(url)
            print(f"  {url}: {len(dados)} bytes")
            print("   ", mascarar(dados.decode("utf-8", "replace"))[:900])
        except Exception as erro:
            print(f"  {url}: {erro}")
    url = "https://portal.tcu.gov.br/carta-de-servicos/certidoes/lista-de-responsaveis-com-contas-julgadas-irregulares-para-fins-eleitorais"
    try:
        pagina = baixar(url).decode("utf-8", "replace")
        links = sorted(set(re.findall(r'href="([^"]+)"', pagina)))
        print(f"  página da lista eleitoral: {len(pagina)} bytes")
        for link in links:
            if re.search(r"(csv|xls|xlsx|pdf|zip|json|irregular|eleit)", link, re.I):
                print("   link:", link)
    except Exception as erro:
        print(f"  {url}: {erro}")


def receita() -> None:
    print("\n=== Receita Federal: CNPJ (sócios)")
    base = "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/"
    try:
        indice = baixar(base).decode("utf-8", "replace")
    except Exception as erro:
        print(f"  {base}: {erro}")
        return
    meses = sorted(set(re.findall(r'href="(\d{4}-\d{2})/?"', indice)))
    print(f"  meses disponíveis (últimos): {meses[-4:]}")
    if not meses:
        print("  ", indice[:800])
        return
    pasta = f"{base}{meses[-1]}/"
    arquivos = re.findall(r'href="([^"]+\.zip)"', baixar(pasta).decode("utf-8", "replace"))
    print(f"  arquivos em {meses[-1]}: {arquivos}")
    socios = [a for a in arquivos if a.lower().startswith("socios")]
    if socios:
        dados = baixar(pasta + socios[0])
        print(f"  {socios[0]}: {len(dados) / 1e6:.0f} MB")
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            nome = z.namelist()[0]
            with z.open(nome) as f:
                for i, linha in enumerate(io.TextIOWrapper(f, encoding="latin-1")):
                    print("   linha:", mascarar(linha.strip())[:300])
                    if i >= 4:
                        break
            print(f"  tamanho descompactado: {z.getinfo(nome).file_size / 1e6:.0f} MB")


if __name__ == "__main__":
    for cadastro in ("ceis", "cnep", "ceaf"):
        portal(cadastro)
    tcu()
    receita()
