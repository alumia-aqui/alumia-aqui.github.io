"""Segunda rodada da Fase 3: origens do CEIS, tamanho da lista do TCU e Receita."""

import csv
import io
import json
import re
import time
import urllib.request
import zipfile
from collections import Counter

CABECALHO = {"User-Agent": "Mozilla/5.0 (alumia-aqui; dados abertos)", "Accept": "*/*"}


def baixar(url: str, tentativas: int = 4) -> bytes:
    for t in range(tentativas):
        try:
            pedido = urllib.request.Request(url, headers=CABECALHO)
            with urllib.request.urlopen(pedido, timeout=300) as r:
                return r.read()
        except Exception as erro:
            print(f"  tentativa {t + 1} falhou: {erro}")
            time.sleep(5 * (t + 1))
    raise RuntimeError(url)


dados = baixar("https://portaldatransparencia.gov.br/download-de-dados/ceis/20261002")
with zipfile.ZipFile(io.BytesIO(dados)) as z:
    texto = z.read(z.namelist()[0]).decode("latin-1")
linhas = list(csv.DictReader(io.StringIO(texto), delimiter=";"))
pf = [l for l in linhas if l["TIPO DE PESSOA"] == "F"]
print(f"CEIS: {len(linhas)} sanções, {len(pf)} de pessoas físicas")
print("  formatos de CPF (PF):", Counter(re.sub(r"\d", "9", l["CPF OU CNPJ DO SANCIONADO"]) for l in pf).most_common(4))
print("  origem (PF):", Counter(l["ORIGEM INFORMAÇÕES"] for l in pf).most_common(8))
print("  categoria (PF):", Counter(l["CATEGORIA DA SANÇÃO"] for l in pf).most_common(8))
print("  esfera (PF):", Counter(l["ESFERA ÓRGÃO SANCIONADOR"] for l in pf).most_common(5))

print("\nTCU inabilitados: paginação")
url = "https://contas.tcu.gov.br/ords/condenacao/consulta/inabilitados"
total, paginas = 0, 0
while url and paginas < 200:
    resposta = json.loads(baixar(url))
    total += len(resposta.get("items", []))
    paginas += 1
    proximo = [l["href"] for l in resposta.get("links", []) if l.get("rel") == "next"]
    url = proximo[0] if proximo else None
print(f"  {total} registros em {paginas} páginas; chaves: {list(resposta['items'][0].keys()) if resposta.get('items') else None}")

print("\nReceita Federal")
for base in (
    "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/",
    "https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/",
):
    try:
        indice = baixar(base).decode("utf-8", "replace")
        meses = sorted(set(re.findall(r'href="(\d{4}-\d{2})/?"', indice)))
        print(f"  {base}: meses {meses[-3:]}")
        if meses:
            pasta = f"{base}{meses[-1]}/"
            listagem = baixar(pasta).decode("utf-8", "replace")
            print("  arquivos:", re.findall(r'href="([^"]+\.zip)"', listagem))
            print("  tamanhos:", re.findall(r'(Socios\d\.zip).{0,200}?(\d+(?:\.\d+)?[KMG])', listagem, re.S)[:10])
            break
    except Exception as erro:
        print(f"  {base}: {erro}")
