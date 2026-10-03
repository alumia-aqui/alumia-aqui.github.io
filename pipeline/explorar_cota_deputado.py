"""Confere a cota parlamentar de um deputado, campo a campo.

Compara o valor do documento, a glosa, o líquido e a restituição, por ano,
para entender diferenças em relação ao site da Câmara.

Uso:  python pipeline/explorar_cota_deputado.py "TABATA AMARAL" 2025 2026
"""

import csv
import io
import sys
import urllib.request
import zipfile
from collections import defaultdict


def numero(texto: str) -> float:
    try:
        return float((texto or "0").replace(",", "."))
    except ValueError:
        return 0.0


nome = sys.argv[1].upper()
anos = [int(a) for a in sys.argv[2:]] or [2025, 2026]
for ano in anos:
    url = f"https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip"
    pedido = urllib.request.Request(url, headers={"User-Agent": "alumia-aqui"})
    with urllib.request.urlopen(pedido, timeout=180) as resposta:
        dados = resposta.read()
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        texto = z.read(z.namelist()[0]).decode("utf-8-sig")
    linhas = [l for l in csv.DictReader(io.StringIO(texto), delimiter=";") if nome in l["txNomeParlamentar"].upper()]
    print(f"\n=== {ano}: {len(linhas)} lançamentos de {sorted({l['txNomeParlamentar'] for l in linhas})}")
    if not linhas:
        continue
    print(f"  ideCadastro: {sorted({l['ideCadastro'] for l in linhas})}")
    soma = defaultdict(float)
    por_mes = defaultdict(float)
    for l in linhas:
        for campo in ("vlrDocumento", "vlrGlosa", "vlrLiquido", "vlrRestituicao"):
            soma[campo] += numero(l[campo])
        por_mes[int(l["numMes"] or 0)] += numero(l["vlrLiquido"])
    for campo, valor in soma.items():
        print(f"  {campo}: R$ {valor:,.2f}")
    print(f"  emissão mais recente: {max(l['datEmissao'][:10] for l in linhas if l['datEmissao'])}")
    print("  líquido por mês:", {m: round(v) for m, v in sorted(por_mes.items())})
    tipos = defaultdict(float)
    for l in linhas:
        tipos[l["indTipoDocumento"]] += numero(l["vlrLiquido"])
    print("  líquido por tipo de documento:", {t: round(v) for t, v in tipos.items()})
