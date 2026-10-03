"""Resumo da ligação com Câmara e Senado, para conferência.

Mostra contagens e alguns exemplos de parlamentares (pessoas públicas, dados
públicos). Não mostra CPF.

Rodar depois de gerar_parlamento.py.
"""

import json
from collections import Counter
from pathlib import Path

PASTA = Path(__file__).parent / "saida" / "pessoas"

pessoas = [json.loads(f.read_text(encoding="utf-8")) for f in PASTA.glob("*.json")]
com = [p for p in pessoas if p.get("parlamento")]
print(f"Pessoas candidatas: {len(pessoas)}; com mandato no Congresso desde 2015: {len(com)}")

casas = Counter(m["casa"] for p in com for m in p["parlamento"]["mandatos"])
print("Mandatos por casa:", dict(casas))

atuais = Counter()
for p in com:
    for m in p["parlamento"]["mandatos"]:
        if m["fim"] >= 2027:
            atuais[m["casa"]] += 1
print("Mandato atual (até 2027) e candidatos agora:", dict(atuais))

cargos = Counter()
for p in com:
    for c in p["candidaturas"]:
        if c["ano"] == 2026:
            cargos[c["cargo"]] += 1
print("Cargo que disputam em 2026:", dict(cargos))

sem_prop = sum(1 for p in com if p["parlamento"]["proposicoes"]["autor"] + p["parlamento"]["proposicoes"]["coautor"] == 0)
sem_cota = sum(1 for p in com if not p["parlamento"]["cota"])
print(f"Sem nenhuma proposição: {sem_prop}; sem gasto de cota: {sem_cota}")

autores = sorted(p["parlamento"]["proposicoes"]["autor"] for p in com)
if autores:
    print(f"Proposições com autoria principal: mediana {autores[len(autores) // 2]}, maior {autores[-1]}")
totais = sorted(c["total"] for p in com for c in p["parlamento"]["cota"] if c["ano"] == 2025)
if totais:
    print(f"Cota 2025 por pessoa: mediana R$ {totais[len(totais) // 2]:,.0f}, maior R$ {totais[-1]:,.0f}")

print("\nExemplos:")
for p in sorted(com, key=lambda p: p["nome"])[::max(1, len(com) // 8)][:8]:
    par = p["parlamento"]
    mand = "; ".join(f"{m['casa']} {m['uf']} {m['inicio']}-{m['fim']}" for m in par["mandatos"])
    cota = ", ".join(f"{c['ano']}: R$ {c['total']:,.0f}" for c in par["cota"][:3])
    print(f"- {p['nome']} | {mand}")
    print(f"    proposições: {par['proposicoes']['autor']} autor, {par['proposicoes']['coautor']} coautor | cota: {cota}")
    for r in par["proposicoes"]["recentes"][:1]:
        print(f"    mais recente: {r['identificacao']} ({r['data']}) {r['situacao']}")

# Páginas da Câmara (legislatura atual).
com_atuacao = [p for p in com if p["parlamento"].get("atuacao_camara")]
print(f"\nCom dados da página da Câmara: {len(com_atuacao)}")
campos = Counter()
for p in com_atuacao:
    for campo, valor in p["parlamento"]["atuacao_camara"][0].items():
        if valor not in (None, 0):
            campos[campo] += 1
print("Campos preenchidos no ano mais recente:", dict(campos))
for p in sorted(com_atuacao, key=lambda p: p["nome"])[:: max(1, len(com_atuacao) // 5)][:5]:
    a = p["parlamento"]["atuacao_camara"][0]
    print(f"- {p['nome']} {a['ano']}: plenário {a['presenca_plenario']}, imóvel {a['imovel_funcional']}, verba {a['verba_gabinete']}")

# Sanções (gerar_sancoes.py).
com_sancao = [p for p in pessoas if (p.get("sancoes") or {}).get("registros")]
print(f"\nCom sanção registrada na CGU: {len(com_sancao)}")
print("Por cadastro:", dict(Counter(s["cadastro"] for p in com_sancao for s in p["sancoes"]["registros"])))
print("Ativas:", sum(1 for p in com_sancao for s in p["sancoes"]["registros"] if s["vigente"]))
print("Categorias:", Counter(s["categoria"] for p in com_sancao for s in p["sancoes"]["registros"]).most_common(6))
print("Origens:", Counter(s["origem"] for p in com_sancao for s in p["sancoes"]["registros"]).most_common(5))
