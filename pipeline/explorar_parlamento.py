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
    senado = "https://legis.senado.leg.br/dadosabertos"
    # Arquivo CSV do Senado: aceitar qualquer tipo de conteúdo.
    CABECALHO["Accept"] = "*/*"
    mostrar_csv(
        "Senado: cota parlamentar (CEAPS) 2025",
        "https://www.senado.leg.br/transparencia/LAI/verba/despesa_ceaps_2025.csv",
        linhas=2,
    )
    CABECALHO["Accept"] = "application/json"
    mostrar_json("Senado: processos de autoria (serviço novo)", f"{senado}/processo?codigoParlamentarAutor=5012&sigla=PL", 2500)
    mostrar_json("Senado: processos, parâmetro alternativo", f"{senado}/processo?autor=Randolfe%20Rodrigues&sigla=PL", 1200)
    mostrar_json("Senado: lista legislatura 55", f"{senado}/senador/lista/legislatura/55.json", 300)

    # Câmara: o CPF vem preenchido na cota parlamentar? E na API, para quantos?
    import collections
    camara = "https://dadosabertos.camara.leg.br"
    dados = baixar("https://www.camara.leg.br/cotas/Ano-2025.csv.zip")
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        texto = z.read(z.namelist()[0]).decode("utf-8-sig")
    linhas = list(csv.DictReader(io.StringIO(texto), delimiter=";"))
    deputados = {l["ideCadastro"]: l for l in linhas if l["ideCadastro"]}
    com_cpf = sum(1 for l in deputados.values() if re.fullmatch(r"\d{11}", l["cpf"] or ""))
    print(f"\n=== Cota 2025: {len(deputados)} deputados, {com_cpf} com CPF preenchido")
    print("  categorias:", collections.Counter(l["txtDescricao"] for l in linhas).most_common(20))
    ids = list(deputados)[:40]
    preenchidos = 0
    for id_ in ids:
        d = json.loads(baixar(f"{camara}/api/v2/deputados/{id_}"))["dados"]
        preenchidos += bool(re.fullmatch(r"\d{11}", d.get("cpf") or ""))
    print(f"  API: {preenchidos} de {len(ids)} deputados com CPF no detalhe")
    mostrar_json("Câmara: situações e tipos de proposição", f"{camara}/api/v2/referencias/proposicoes/codSituacao", 1500)


if __name__ == "__main__":
    main()
