"""Junta aos Retratos as empresas de dados/empresas.json (gerado por gerar_empresas.py).

Também marca as empresas com sanção ativa ou encerrada no CEIS ou no CNEP
(punições de empresas, CGU), pelo CNPJ.

Rodar depois de gerar_sancoes.py, que baixa os cadastros da CGU:
    python pipeline/juntar_empresas.py
"""

import json
import re
from pathlib import Path

from gerar_pessoas import PASTA_SAIDA
from gerar_sancoes import baixar_cadastro, data_iso, linhas_cadastro

ARQUIVO = Path(__file__).parent.parent / "dados" / "empresas.json"


def sancoes_de_empresas() -> dict[str, list[dict]]:
    """CNPJ (14 caracteres) -> sanções de pessoa jurídica no CEIS e no CNEP."""
    por_cnpj: dict[str, list[dict]] = {}
    for cadastro in ("ceis", "cnep"):
        try:
            dados = baixar_cadastro(cadastro)
        except Exception as erro:
            print(f"  {cadastro.upper()}: {erro}")
            continue
        for linha in linhas_cadastro(dados):
            if linha.get("TIPO DE PESSOA") != "J":
                continue
            cnpj = re.sub(r"[^0-9A-Z]", "", linha.get("CPF OU CNPJ DO SANCIONADO", "").upper())
            if len(cnpj) != 14:
                continue
            fim = data_iso(linha.get("DATA FINAL SANÇÃO", ""))
            por_cnpj.setdefault(cnpj, []).append({
                "cadastro": cadastro.upper(),
                "codigo": linha.get("CÓDIGO DA SANÇÃO"),
                "categoria": linha.get("CATEGORIA DA SANÇÃO") or None,
                "orgao": linha.get("ÓRGÃO SANCIONADOR") or None,
                "inicio": data_iso(linha.get("DATA INÍCIO SANÇÃO", "")),
                "fim": fim,
            })
    return por_cnpj


def main() -> None:
    if not ARQUIVO.exists():
        print("Empresas: dados/empresas.json não existe ainda; seção não será gerada.")
        return
    empresas = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    sancoes = sancoes_de_empresas()

    total, com_sancao = 0, 0
    for caminho in (PASTA_SAIDA / "pessoas").glob("*.json"):
        pessoa = json.loads(caminho.read_text(encoding="utf-8"))
        registros = []
        for e in empresas["pessoas"].get(pessoa["id"], []):
            e = dict(e)
            e["sancoes"] = sancoes.get((e.get("cnpj") or "").upper(), [])
            com_sancao += bool(e["sancoes"])
            registros.append(e)
        total += bool(registros)
        pessoa["empresas"] = {"referencia": empresas["referencia"], "registros": registros}
        caminho.write_text(json.dumps(pessoa, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Empresas ({empresas['referencia']}): {total} candidatos sócios; {com_sancao} vínculos com empresa sancionada")


if __name__ == "__main__":
    main()
