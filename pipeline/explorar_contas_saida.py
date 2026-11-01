"""Resumo das contas de campanha geradas, para conferência. Rodar depois de gerar_contas.py."""

import json
from collections import Counter
from pathlib import Path

PASTA = Path(__file__).parent / "saida" / "pessoas"
pessoas = [json.loads(f.read_text(encoding="utf-8")) for f in PASTA.glob("*.json")]
com = [p for p in pessoas if p.get("campanha")]
print(f"{len(com)} de {len(pessoas)} pessoas com contas")

tipos = Counter((p["campanha"]["prestacao"] or {}).get("tipo") for p in com)
print("tipo de prestação:", tipos.most_common())

sem_receita = sum(1 for p in com if not p["campanha"]["receitas"]["total"])
print("sem receita declarada:", sem_receita)

maiores = sorted(com, key=lambda p: p["campanha"]["receitas"]["total"], reverse=True)[:3]
for p in maiores:
    c = p["campanha"]
    cargo = p["candidaturas"][0]["cargo"]
    print(f"\n{p['nome']} ({cargo})")
    print(json.dumps(c, ensure_ascii=False, indent=1)[:1200])

medios = [p for p in com if 10_000 < p["campanha"]["receitas"]["total"] < 100_000][:2]
for p in medios:
    print(f"\n{p['nome']}: {json.dumps(p['campanha'], ensure_ascii=False)[:700]}")
