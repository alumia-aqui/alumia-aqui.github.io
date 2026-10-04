"""Gera os dados do painel do Congresso: todos os parlamentares em exercício.

Diferente dos Retratos, que só existem para quem é candidato, o painel cobre os
513 deputados e os 81 senadores em exercício, para que os números por partido e
por estado sejam completos.

Para cada parlamentar:
- Casa, nome parlamentar, partido atual e UF, segundo a Câmara e o Senado.
- Projetos apresentados como autor principal desde o início da legislatura
  atual (PL, PLP, PEC e PDL).
- Gasto da cota parlamentar (valor reembolsado) por ano, desde o início da
  legislatura atual.
- Código do Retrato, quando a pessoa é candidata na eleição atual. A ligação
  segue as mesmas regras de gerar_parlamento.py (CPF na Câmara; nome completo e
  data de nascimento no Senado).

Usa os arquivos já baixados por gerar_parlamento.py e baixa o que faltar.
Rodar depois dele:  python pipeline/gerar_congresso.py
Saída: pipeline/saida/congresso.json
"""

import json
from collections import Counter, defaultdict
from datetime import date

import gerar_parlamento as gp
from gerar_pessoas import PASTA_SAIDA, carregar_chave

LEGISLATURA = max(gp.LEGISLATURAS)
INICIO, _ = gp.LEGISLATURAS[LEGISLATURA]
DATA_INICIO = f"{INICIO}-02-01"
ANOS = range(INICIO, gp.ANO_ATUAL + 1)
SITUACOES_SENADO: Counter = Counter()  # para conferência no registro da execução


def deputados() -> dict[str, dict]:
    resposta = gp.pedir_json(f"{gp.CAMARA}/api/v2/deputados?itens=1000&ordem=ASC&ordenarPor=nome")
    return {
        str(d["id"]): {
            "casa": "Câmara",
            "nome": d["nome"],
            "partido": d["siglaPartido"],
            "uf": d["siglaUf"],
            "url": f"https://www.camara.leg.br/deputados/{d['id']}",
        }
        for d in resposta["dados"]
    }


def senadores() -> dict[str, dict]:
    resposta = gp.pedir_json(f"{gp.SENADO}/senador/lista/atual.json")
    lista = resposta["ListaParlamentarEmExercicio"]["Parlamentares"]["Parlamentar"]
    saida = {}
    for p in gp.lista(lista):
        ident = p["IdentificacaoParlamentar"]
        partido = ident.get("SiglaPartidoParlamentar")
        saida[ident["CodigoParlamentar"]] = {
            "casa": "Senado",
            "nome": ident["NomeParlamentar"],
            "nome_completo": ident.get("NomeCompletoParlamentar"),
            "partido": None if partido in (None, "S/Partido") else partido,
            "uf": ident.get("UfParlamentar"),
            "participacao": (p.get("Mandato") or {}).get("DescricaoParticipacao"),
            "url": f"https://www25.senado.leg.br/web/senadores/senador/-/perfil/{ident['CodigoParlamentar']}",
        }
    return saida


def retratos_camara(chave: bytes, ids_pessoas: set[str]) -> dict[str, str]:
    """id do deputado -> código do Retrato, pelo cache de CPF de gerar_parlamento.py."""
    caminho = gp.PASTA / f"deputados_pessoas_{gp.impressao(chave)}.json"
    cache = json.loads(caminho.read_text()) if caminho.exists() else {}
    return {d: p for d, p in cache.items() if p in ids_pessoas}


def retratos_senado(sen: dict[str, dict], pessoas: list[dict]) -> dict[str, str]:
    """Código do senador -> código do Retrato, por nome completo e data de nascimento."""
    caminho = gp.PASTA / "senadores_detalhe.json"
    cache = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
    por_nome = {
        (gp.normalizar(p["nome"]), p["data_nascimento"]): p["id"]
        for p in pessoas if p.get("data_nascimento")
    }
    ligados = {}
    for codigo in sen:
        detalhe = cache.get(codigo)
        if not detalhe or not detalhe.get("nascimento"):
            continue
        ano, mes, dia = detalhe["nascimento"][:10].split("-")
        id_pessoa = por_nome.get((gp.normalizar(detalhe["nome_completo"]), f"{dia}/{mes}/{ano}"))
        if id_pessoa:
            ligados[codigo] = id_pessoa
    return ligados


def virou_lei(situacao: str | None) -> bool:
    """Situação final de proposição transformada em lei ou emenda constitucional."""
    texto = gp.normalizar(situacao)
    return "TRANSFORMAD" in texto and "NORMA" in texto


def projetos_camara(dep: dict[str, dict]) -> tuple[dict[str, int], dict[str, int]]:
    """Projetos com autoria principal, apresentados desde o início da legislatura,
    e quantos deles viraram norma jurídica (lei ou emenda constitucional)."""
    contagem: dict[str, int] = defaultdict(int)
    leis: dict[str, int] = defaultdict(int)
    for ano in ANOS:
        autores = gp.arquivo(
            f"{gp.CAMARA}/arquivos/proposicoesAutores/csv/proposicoesAutores-{ano}.csv",
            f"camara_autores_{ano}.csv", ano,
        )
        proposicoes = gp.arquivo(
            f"{gp.CAMARA}/arquivos/proposicoes/csv/proposicoes-{ano}.csv",
            f"camara_proposicoes_{ano}.csv", ano,
        )
        if autores is None or proposicoes is None:
            continue
        validas = {
            linha["id"]: virou_lei(linha["ultimoStatus_descricaoSituacao"])
            for linha in gp.ler_csv(proposicoes)
            if linha["siglaTipo"] in gp.TIPOS and linha["dataApresentacao"][:10] >= DATA_INICIO
        }
        for linha in gp.ler_csv(autores):
            if (linha["idProposicao"] in validas and linha["ordemAssinatura"] == "1"
                    and linha["idDeputadoAutor"] in dep):
                contagem[linha["idDeputadoAutor"]] += 1
                leis[linha["idDeputadoAutor"]] += validas[linha["idProposicao"]]
    return contagem, leis


def projetos_senado(sen: dict[str, dict]) -> tuple[dict[str, int], dict[str, int], list[str]]:
    contagem: dict[str, int] = defaultdict(int)
    leis: dict[str, int] = defaultdict(int)
    falhas = []
    for codigo, s in sen.items():
        nome = gp.normalizar(s["nome"])
        vistas = set()
        for sigla in gp.TIPOS:
            try:
                materias = gp.materias_senado(codigo, sigla)
            except Exception as erro:  # uma consulta com falha não derruba as demais
                falhas.append(f"{s['nome']} ({sigla}): {erro}")
                continue
            for m in materias:
                if (m.get("dataApresentacao") or "")[:10] < DATA_INICIO:
                    continue
                primeiro = gp.normalizar((m.get("autoria") or "").split("(")[0].split(",")[0])
                if primeiro.endswith(nome) and m.get("codigoMateria") not in vistas:
                    vistas.add(m.get("codigoMateria"))
                    contagem[codigo] += 1
                    leis[codigo] += virou_lei(m.get("situacaoAtual"))
                    SITUACOES_SENADO[m.get("situacaoAtual")] += 1
    return contagem, leis, falhas


def cota(dep: dict[str, dict], sen: dict[str, dict]) -> dict[tuple[str, str], dict[int, float]]:
    """(casa, código) -> {ano: valor reembolsado}."""
    gastos: dict[tuple[str, str], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    senador_por_nome = {gp.normalizar(s["nome"]): c for c, s in sen.items()}
    for ano in ANOS:
        caminho = gp.arquivo(f"https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip", f"camara_cota_{ano}.zip", ano)
        if caminho:
            for linha in gp.ler_csv(caminho):
                if linha["ideCadastro"] in dep:
                    gastos[("Câmara", linha["ideCadastro"])][ano] += gp.tse.valor_em_reais(linha["vlrLiquido"]) or 0
        caminho = gp.arquivo(
            f"https://www.senado.leg.br/transparencia/LAI/verba/despesa_ceaps_{ano}.csv",
            f"senado_cota_{ano}.csv", ano,
        )
        if caminho:
            for linha in gp.ler_csv(caminho, pular=1):
                codigo = senador_por_nome.get(gp.normalizar(linha.get("SENADOR")))
                if codigo:
                    gastos[("Senado", codigo)][ano] += gp.tse.valor_em_reais(linha.get("VALOR_REEMBOLSADO")) or 0
    return gastos


def main() -> None:
    chave = carregar_chave()
    pessoas = [json.loads(f.read_text(encoding="utf-8")) for f in (PASTA_SAIDA / "pessoas").glob("*.json")]
    ids_pessoas = {p["id"] for p in pessoas}

    dep, sen = deputados(), senadores()
    print(f"Em exercício: {len(dep)} deputados e {len(sen)} senadores")

    retrato = {("Câmara", d): p for d, p in retratos_camara(chave, ids_pessoas).items() if d in dep}
    retrato |= {("Senado", s): p for s, p in retratos_senado(sen, pessoas).items()}
    print(f"Com Retrato (candidatos agora): {len(retrato)}")

    contagem_camara, leis_camara = projetos_camara(dep)
    contagem_senado, leis_senado, falhas = projetos_senado(sen)
    projetos = {("Câmara", d): n for d, n in contagem_camara.items()}
    projetos |= {("Senado", s): n for s, n in contagem_senado.items()}
    leis = {("Câmara", d): n for d, n in leis_camara.items()}
    leis |= {("Senado", s): n for s, n in leis_senado.items()}
    print("Situações mais comuns no Senado:", SITUACOES_SENADO.most_common(12))
    if falhas:
        print(f"{len(falhas)} consultas de proposições do Senado falharam, por exemplo: {falhas[:3]}")
    gastos = cota(dep, sen)

    parlamentares = []
    for casa, grupo in (("Câmara", dep), ("Senado", sen)):
        for codigo, p in grupo.items():
            chave_p = (casa, codigo)
            parlamentares.append({
                "casa": casa,
                "nome": p["nome"],
                "partido": p["partido"],
                "uf": p["uf"],
                "participacao": p.get("participacao"),
                "url": p["url"],
                "retrato": retrato.get(chave_p),
                "projetos": projetos.get(chave_p, 0),
                "leis": leis.get(chave_p, 0),
                "cota": {str(ano): round(gastos[chave_p].get(ano, 0), 2) for ano in ANOS},
            })
    parlamentares.sort(key=lambda p: gp.normalizar(p["nome"]))

    saida = {
        "consultado_em": date.today().isoformat(),
        "legislatura": {"numero": LEGISLATURA, "inicio": DATA_INICIO},
        "anos_cota": list(ANOS),
        "parlamentares": parlamentares,
    }
    destino = PASTA_SAIDA / "congresso.json"
    destino.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sem_cota = sum(1 for p in parlamentares if not any(p["cota"].values()))
    print(f"Gerado {destino.name}: {len(parlamentares)} parlamentares, "
          f"{sum(p['projetos'] for p in parlamentares)} projetos ({sum(p['leis'] for p in parlamentares)} viraram norma), {sem_cota} sem gasto de cota registrado")


if __name__ == "__main__":
    main()
