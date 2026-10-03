"""Confere o formato das listas de parlamentares em exercício e dos arquivos de cota.

Usado para montar o painel do Congresso (gerar_congresso.py). Mostra só dados
públicos de parlamentares; nenhum CPF.
"""

import json
from collections import Counter

import gerar_parlamento as gp

print("== Câmara: deputados em exercício")
resposta = gp.pedir_json(f"{gp.CAMARA}/api/v2/deputados?itens=1000&ordem=ASC&ordenarPor=nome")
dados = resposta["dados"]
print("quantidade:", len(dados), "links:", [l["rel"] for l in resposta["links"]])
print(json.dumps(dados[0], ensure_ascii=False))
print("partidos:", Counter(d["siglaPartido"] for d in dados).most_common())

print("\n== Senado: senadores em exercício")
resposta = gp.pedir_json(f"{gp.SENADO}/senador/lista/atual.json")
print("chaves:", list(resposta.keys()))
lista = resposta["ListaParlamentarEmExercicio"]["Parlamentares"]["Parlamentar"]
print("quantidade:", len(lista))
print(json.dumps(lista[0], ensure_ascii=False)[:1500])
print("partidos:", Counter(p["IdentificacaoParlamentar"].get("SiglaPartidoParlamentar") for p in lista).most_common())
print("participação:", Counter((p.get("Mandato") or {}).get("DescricaoParticipacao") for p in lista))

print("\n== Arquivos de cota no cache")
for nome in sorted(p.name for p in gp.PASTA.glob("*cota*")):
    print(nome)
for nome, pular in (("camara_cota_2025.zip", 0), ("senado_cota_2025.csv", 1)):
    caminho = gp.PASTA / nome
    if caminho.exists():
        linhas = gp.ler_csv(caminho, pular=pular)
        primeira = next(linhas)
        print(nome, "colunas:", list(primeira.keys()))
        print("  exemplo:", {k: primeira[k] for k in list(primeira)[:30] if "cpf" not in k.lower()})

print("\n== Arquivos de proposições no cache")
for nome in sorted(p.name for p in gp.PASTA.glob("camara_*.csv")):
    print(nome)
