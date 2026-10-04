"""Mostra um resumo de saida/congresso.json, para conferência. Rodar depois de gerar_congresso.py."""

import json
from collections import Counter
from pathlib import Path

d = json.loads((Path(__file__).parent / "saida" / "congresso.json").read_text(encoding="utf-8"))
ps = d["parlamentares"]
print("anos de cota:", d["anos_cota"])
for p in ps[:3] + [p for p in ps if p["casa"] == "Senado"][:3]:
    print(json.dumps(p, ensure_ascii=False))
print("sem projetos:", sum(1 for p in ps if not p["projetos"]))
print("com lei:", sum(1 for p in ps if p["leis"]), "total de leis:", sum(p["leis"] for p in ps))
print("sem cota em 2025:", [(p["nome"], p["casa"]) for p in ps if not p["cota"]["2025"]][:25])
print("sem partido:", [(p["nome"], p["casa"]) for p in ps if not p["partido"]])
por_casa = Counter(p["casa"] for p in ps)
for casa in por_casa:
    grupo = [p for p in ps if p["casa"] == casa]
    print(casa, len(grupo), "cota 2025 média:", round(sum(p["cota"]["2025"] for p in grupo) / len(grupo)),
          "projetos média:", round(sum(p["projetos"] for p in grupo) / len(grupo), 1))
