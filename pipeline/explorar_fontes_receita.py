"""Valores reais das colunas de fonte e origem das receitas de campanha.

Serve para saber o que é dinheiro público (Fundo Eleitoral e Fundo Partidário).
Rodar:  python pipeline/explorar_fontes_receita.py
"""

from collections import Counter, defaultdict

import tse
from gerar_contas import URL, ler

ANO = 2026
caminho = tse.baixar_url(URL.format(ano=ANO), tse.PASTA_DADOS / f"contas_candidatos_{ANO}.zip")

contagem: dict[str, Counter] = defaultdict(Counter)
soma: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
for linha in ler(caminho, "receitas_candidatos", ANO):
    valor = tse.valor_em_reais(linha.get("VR_RECEITA")) or 0
    for coluna in ("DS_FONTE_RECEITA", "DS_ORIGEM_RECEITA", "DS_NATUREZA_RECEITA", "DS_ESPECIE_RECEITA"):
        chave = (linha.get(coluna) or "").strip()
        contagem[coluna][chave] += 1
        soma[coluna][chave] += valor

for coluna, valores in contagem.items():
    print(f"\n== {coluna}")
    for nome, n in valores.most_common(12):
        print(f"  {n:>9}  R$ {soma[coluna][nome]:>18,.2f}  {nome!r}")
