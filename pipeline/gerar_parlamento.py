"""Junta aos Retratos os mandatos na Câmara e no Senado, desde 2015.

Para cada pessoa candidata que foi deputada federal ou senadora:
- Mandatos: casa, período, UF e partido (ou participação, no Senado).
- Proposições: projetos de lei (PL, PLP), PECs e PDLs em que é autora ou coautora.
- Cota parlamentar: gastos por ano e por categoria.
- Deputados da legislatura atual: presença, salário, imóvel funcional,
  auxílio-moradia, verba e pessoal de gabinete e viagens, lidos da página do
  deputado no site da Câmara (camara_pagina.py), porque não estão nos dados abertos.

Ligação com as pessoas do TSE:
- Câmara: pelo CPF, que a API da Câmara publica no detalhe de cada deputado.
  O CPF vira o mesmo código HMAC usado em gerar_pessoas.py e não é guardado.
- Senado: o Senado não publica CPF. A ligação usa nome completo e data de
  nascimento, que precisam ser iguais aos do TSE.

Rodar depois de gerar_pessoas.py:  python pipeline/gerar_parlamento.py
"""

import csv
import hashlib
import http.client
import hmac
import io
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import camara_pagina
import tse
from gerar_pessoas import PASTA_SAIDA, carregar_chave, codigo_pessoa

CAMARA = "https://dadosabertos.camara.leg.br"
SENADO = "https://legis.senado.leg.br/dadosabertos"
PASTA = tse.PASTA_DADOS / "parlamento"

LEGISLATURAS = {55: (2015, 2019), 56: (2019, 2023), 57: (2023, 2027)}
PRIMEIRO_ANO = 2015
ANO_ATUAL = date.today().year
ANOS = range(PRIMEIRO_ANO, ANO_ATUAL + 1)

TIPOS = {
    "PL": "Projeto de lei",
    "PLP": "Projeto de lei complementar",
    "PEC": "Proposta de emenda à Constituição",
    "PDL": "Projeto de decreto legislativo",
}
RECENTES = 10
TEMPO_PAGINAS_CAMARA = 25 * 60  # segundos por execução


# ---------------------------------------------------------------- utilidades

def pedir(url: str, aceitar: str = "application/json", tentativas: int = 4) -> bytes:
    pedido = urllib.request.Request(
        url, headers={"User-Agent": "alumia-aqui (dados abertos)", "Accept": aceitar}
    )
    for tentativa in range(tentativas):
        try:
            with urllib.request.urlopen(pedido, timeout=180) as resposta:
                return resposta.read()
        except urllib.error.HTTPError as erro:
            if erro.code == 404 or tentativa == tentativas - 1:
                raise
        except (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError):
            # Inclui resposta cortada no meio (IncompleteRead).
            if tentativa == tentativas - 1:
                raise
        time.sleep(2 ** tentativa)
    raise RuntimeError("inalcançável")


def pedir_json(url: str):
    return json.loads(pedir(url))


def arquivo(url: str, nome: str, ano: int) -> Path | None:
    """Baixa e guarda um arquivo. O do ano atual vale um dia; os anteriores, uma semana."""
    destino = PASTA / nome
    validade = 1 if ano >= ANO_ATUAL else 7
    if destino.exists() and time.time() - destino.stat().st_mtime < validade * 86400:
        return destino
    PASTA.mkdir(parents=True, exist_ok=True)
    print(f"Baixando {url}")
    try:
        dados = pedir(url, aceitar="*/*")
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            print(f"  não encontrado: {url}")
            return destino if destino.exists() else None
        raise
    temporario = destino.with_suffix(".parcial")
    temporario.write_bytes(dados)
    temporario.replace(destino)
    return destino


def ler_csv(caminho: Path, separador: str = ";", pular: int = 0):
    dados = caminho.read_bytes()
    if caminho.suffix == ".zip":
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            dados = z.read(z.namelist()[0])
    try:
        texto = dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = dados.decode("latin-1")
    linhas = io.StringIO(texto)
    for _ in range(pular):
        linhas.readline()
    csv.field_size_limit(10_000_000)
    yield from csv.DictReader(linhas, delimiter=separador)


def lista(valor) -> list:
    if valor is None:
        return []
    return valor if isinstance(valor, list) else [valor]


def normalizar(texto: str | None) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^A-Za-z ]", " ", texto).upper().split())


def impressao(chave: bytes) -> str:
    """Identifica a chave sem revelá-la, para invalidar caches feitos com outra chave."""
    return hmac.new(chave, b"impressao", hashlib.sha256).hexdigest()[:8]


def novo_registro() -> dict:
    return {
        "mandatos": [], "perfis": [], "proposicoes": [], "atuacao_camara": [],
        "cota": defaultdict(lambda: defaultdict(float)),
    }


# ---------------------------------------------------------------- Câmara

def camara(chave: bytes, ids_pessoas: set[str], registros: dict) -> None:
    print("\nCâmara dos Deputados")
    deputados: dict[str, dict] = {}
    for legislatura, (inicio, fim) in LEGISLATURAS.items():
        pagina = 1
        while True:
            resposta = pedir_json(
                f"{CAMARA}/api/v2/deputados?idLegislatura={legislatura}&itens=100&pagina={pagina}"
            )
            for d in resposta["dados"]:
                dep = deputados.setdefault(str(d["id"]), {"nome": d["nome"], "mandatos": []})
                dep["mandatos"].append({
                    "casa": "Câmara dos Deputados", "inicio": inicio, "fim": fim,
                    "uf": d["siglaUf"], "partido": d["siglaPartido"],
                })
            if not any(link["rel"] == "next" for link in resposta["links"]):
                break
            pagina += 1
    print(f"  {len(deputados)} deputados desde {PRIMEIRO_ANO}")

    # CPF -> código da pessoa. O cache guarda só o código, nunca o CPF.
    caminho_cache = PASTA / f"deputados_pessoas_{impressao(chave)}.json"
    cache = json.loads(caminho_cache.read_text()) if caminho_cache.exists() else {}
    for id_deputado in deputados:
        if id_deputado in cache:
            continue
        detalhe = pedir_json(f"{CAMARA}/api/v2/deputados/{id_deputado}")["dados"]
        cpf = re.sub(r"\D", "", detalhe.get("cpf") or "")
        cache[id_deputado] = codigo_pessoa(cpf, chave) if len(cpf) == 11 else None
        time.sleep(0.05)
    PASTA.mkdir(parents=True, exist_ok=True)
    caminho_cache.write_text(json.dumps(cache))

    ligados = {d: p for d, p in cache.items() if d in deputados and p in ids_pessoas}
    print(f"  {len(ligados)} deputados são candidatos agora (ligados pelo CPF)")
    for id_deputado, id_pessoa in ligados.items():
        registro = registros.setdefault(id_pessoa, novo_registro())
        registro["mandatos"].extend(deputados[id_deputado]["mandatos"])
        registro["perfis"].append({
            "casa": "Câmara dos Deputados",
            "url": f"https://www.camara.leg.br/deputados/{id_deputado}",
        })

    paginas_camara(deputados, ligados, registros)

    # Proposições: autores de cada ano e, depois, os dados de cada proposição.
    for ano in ANOS:
        caminho = arquivo(
            f"{CAMARA}/arquivos/proposicoesAutores/csv/proposicoesAutores-{ano}.csv",
            f"camara_autores_{ano}.csv", ano,
        )
        if caminho is None:
            continue
        autorias = defaultdict(list)  # id da proposição -> [(pessoa, principal)]
        for linha in ler_csv(caminho):
            id_pessoa = ligados.get(linha["idDeputadoAutor"])
            if id_pessoa:
                autorias[linha["idProposicao"]].append((id_pessoa, linha["ordemAssinatura"] == "1"))
        if not autorias:
            continue
        caminho = arquivo(
            f"{CAMARA}/arquivos/proposicoes/csv/proposicoes-{ano}.csv",
            f"camara_proposicoes_{ano}.csv", ano,
        )
        if caminho is None:
            continue
        for linha in ler_csv(caminho):
            if linha["siglaTipo"] not in TIPOS or linha["id"] not in autorias:
                continue
            for id_pessoa, principal in autorias[linha["id"]]:
                registros[id_pessoa]["proposicoes"].append({
                    "casa": "Câmara dos Deputados",
                    "tipo": linha["siglaTipo"],
                    "identificacao": f"{linha['siglaTipo']} {linha['numero']}/{linha['ano']}",
                    "ementa": linha["ementa"].strip(),
                    "data": linha["dataApresentacao"][:10],
                    "situacao": linha["ultimoStatus_descricaoSituacao"] or None,
                    "principal": principal,
                    "url": f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={linha['id']}",
                })

    # Cota parlamentar (CEAP).
    for ano in ANOS:
        caminho = arquivo(f"https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip", f"camara_cota_{ano}.zip", ano)
        if caminho is None:
            continue
        for linha in ler_csv(caminho):
            id_pessoa = ligados.get(linha["ideCadastro"])
            valor = tse.valor_em_reais(linha["vlrLiquido"])
            if id_pessoa and valor:
                categoria = linha["txtDescricao"].strip().rstrip(".").strip()
                registros[id_pessoa]["cota"][("Câmara dos Deputados", ano)][categoria] += valor


def paginas_camara(deputados: dict, ligados: dict, registros: dict) -> None:
    """Lê a página de cada deputado da legislatura atual, um ano por vez, desde o início dela."""
    legislatura_atual = max(LEGISLATURAS)
    inicio, _ = LEGISLATURAS[legislatura_atual]
    pasta = PASTA / "camara_paginas"
    pasta.mkdir(parents=True, exist_ok=True)
    lidos, falhas = 0, []
    # Limites para não travar a publicação: o que faltar fica para a próxima execução.
    prazo = time.time() + TEMPO_PAGINAS_CAMARA
    falhas_seguidas = 0
    interrompido = None
    for id_deputado, id_pessoa in ligados.items():
        if not any(m["inicio"] == inicio for m in deputados[id_deputado]["mandatos"]):
            continue
        anos = []
        for ano in range(inicio, ANO_ATUAL + 1):
            destino = pasta / f"{id_deputado}_{ano}.json"
            validade = 1 if ano >= ANO_ATUAL else 30
            atualizado = destino.exists() and time.time() - destino.stat().st_mtime < validade * 86400
            if not atualizado and interrompido is None:
                if time.time() > prazo:
                    interrompido = "tempo esgotado"
                elif falhas_seguidas >= 10:
                    interrompido = "10 falhas seguidas"
            if atualizado or (interrompido and destino.exists()):
                dados = json.loads(destino.read_text(encoding="utf-8"))
            elif interrompido:
                continue
            else:
                try:
                    dados = camara_pagina.ler(camara_pagina.baixar(id_deputado, ano))
                except Exception as erro:
                    falhas.append(f"{deputados[id_deputado]['nome']} {ano}: {erro}")
                    falhas_seguidas += 1
                    continue
                falhas_seguidas = 0
                destino.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
                lidos += 1
                time.sleep(0.2)
            if any(valor not in (None, 0) for valor in dados.values()):
                anos.append({"ano": ano, **dados})
        if anos:
            registros[id_pessoa]["atuacao_camara"] = sorted(anos, key=lambda a: a["ano"], reverse=True)
    com_presenca = sum(
        1 for r in registros.values() if any(a.get("presenca_plenario") for a in r["atuacao_camara"])
    )
    print(f"  Páginas da Câmara: {lidos} lidas agora; {com_presenca} deputados com presença registrada")
    if interrompido:
        print(f"  Leitura interrompida ({interrompido}); o restante fica para a próxima execução.")
    if falhas:
        print(f"  {len(falhas)} páginas não puderam ser lidas, por exemplo: {falhas[:3]}")


# ---------------------------------------------------------------- Senado

def materias_senado(codigo: str, sigla: str) -> list:
    """Proposições de um senador, guardadas por uma semana (a consulta é lenta)."""
    destino = PASTA / "senado_materias" / f"{codigo}_{sigla}.json"
    if destino.exists() and time.time() - destino.stat().st_mtime < 7 * 86400:
        return json.loads(destino.read_text(encoding="utf-8"))
    materias = pedir_json(f"{SENADO}/processo?codigoParlamentarAutor={codigo}&sigla={sigla}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(materias, ensure_ascii=False), encoding="utf-8")
    return materias


def senado(pessoas: list[dict], registros: dict) -> None:
    print("\nSenado Federal")
    senadores: dict[str, dict] = {}
    for legislatura in LEGISLATURAS:
        resposta = pedir_json(f"{SENADO}/senador/lista/legislatura/{legislatura}.json")
        parlamentares = resposta["ListaParlamentarLegislatura"]["Parlamentares"]["Parlamentar"]
        for p in lista(parlamentares):
            ident = p["IdentificacaoParlamentar"]
            sen = senadores.setdefault(ident["CodigoParlamentar"], {"nome": ident["NomeParlamentar"], "mandatos": {}})
            for m in lista((p.get("Mandatos") or {}).get("Mandato")):
                primeira = m.get("PrimeiraLegislaturaDoMandato") or {}
                ultima = m.get("SegundaLegislaturaDoMandato") or primeira
                if not primeira.get("DataInicio"):
                    continue
                sen["mandatos"][m.get("CodigoMandato") or primeira["DataInicio"]] = {
                    "casa": "Senado Federal",
                    "inicio": int(primeira["DataInicio"][:4]),
                    "fim": int(ultima["DataFim"][:4]),
                    "uf": m.get("UfParlamentar"),
                    "participacao": m.get("DescricaoParticipacao"),
                }
    print(f"  {len(senadores)} senadores e suplentes desde {PRIMEIRO_ANO}")

    # Nome completo e data de nascimento vêm do detalhe de cada senador.
    caminho_cache = PASTA / "senadores_detalhe.json"
    cache = json.loads(caminho_cache.read_text()) if caminho_cache.exists() else {}
    for codigo in senadores:
        if codigo not in cache:
            detalhe = pedir_json(f"{SENADO}/senador/{codigo}.json")["DetalheParlamentar"]["Parlamentar"]
            cache[codigo] = {
                "nome_completo": detalhe["IdentificacaoParlamentar"].get("NomeCompletoParlamentar"),
                "nascimento": (detalhe.get("DadosBasicosParlamentar") or {}).get("DataNascimento"),
            }
            time.sleep(0.05)
    PASTA.mkdir(parents=True, exist_ok=True)
    caminho_cache.write_text(json.dumps(cache, ensure_ascii=False))

    por_nome_e_nascimento = {}
    for pessoa in pessoas:
        if pessoa.get("data_nascimento"):
            por_nome_e_nascimento[(normalizar(pessoa["nome"]), pessoa["data_nascimento"])] = pessoa["id"]

    ligados: dict[str, str] = {}
    for codigo, detalhe in cache.items():
        if codigo not in senadores or not detalhe["nascimento"]:
            continue
        ano, mes, dia = detalhe["nascimento"][:10].split("-")
        chave = (normalizar(detalhe["nome_completo"]), f"{dia}/{mes}/{ano}")
        if chave in por_nome_e_nascimento:
            ligados[codigo] = por_nome_e_nascimento[chave]
    print(f"  {len(ligados)} senadores são candidatos agora (ligados por nome completo e nascimento)")

    falhas: list[str] = []
    for codigo, id_pessoa in ligados.items():
        registro = registros.setdefault(id_pessoa, novo_registro())
        registro["mandatos"].extend(senadores[codigo]["mandatos"].values())
        registro["perfis"].append({
            "casa": "Senado Federal",
            "url": f"https://www25.senado.leg.br/web/senadores/senador/-/perfil/{codigo}",
        })
        nome = normalizar(senadores[codigo]["nome"])
        for sigla in TIPOS:
            try:
                materias = materias_senado(codigo, sigla)
            except Exception as erro:  # uma consulta com falha não derruba as demais
                falhas.append(f"{senadores[codigo]['nome']} ({sigla}): {erro}")
                continue
            for m in materias:
                data = (m.get("dataApresentacao") or "")[:10]
                if data[:4] < str(PRIMEIRO_ANO):
                    continue
                # Autoria: "Senador Fulano (PART/UF), Senadora Beltrana (...)". O primeiro é o principal.
                primeiro = normalizar(re.split(r"\(|,", m.get("autoria") or "")[0])
                registro["proposicoes"].append({
                    "casa": "Senado Federal",
                    "tipo": sigla,
                    "identificacao": m.get("identificacao"),
                    "ementa": (m.get("ementa") or "").strip(),
                    "data": data,
                    "situacao": m.get("situacaoAtual"),
                    "principal": primeiro.endswith(nome),
                    "url": f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{m.get('codigoMateria')}",
                })

    if falhas:
        print(f"  {len(falhas)} consultas de proposições falharam e ficaram de fora:")
        for falha in falhas[:10]:
            print(f"    {falha}")

    # Cota parlamentar (CEAPS). A primeira linha do arquivo é a data de atualização.
    por_nome = {normalizar(senadores[c]["nome"]): p for c, p in ligados.items()}
    for ano in ANOS:
        caminho = arquivo(
            f"https://www.senado.leg.br/transparencia/LAI/verba/despesa_ceaps_{ano}.csv",
            f"senado_cota_{ano}.csv", ano,
        )
        if caminho is None:
            continue
        for linha in ler_csv(caminho, pular=1):
            id_pessoa = por_nome.get(normalizar(linha.get("SENADOR")))
            valor = tse.valor_em_reais(linha.get("VALOR_REEMBOLSADO"))
            if id_pessoa and valor:
                categoria = (linha.get("TIPO_DESPESA") or "Outros").strip()
                registros[id_pessoa]["cota"][("Senado Federal", ano)][categoria] += valor


# ---------------------------------------------------------------- saída

def finalizar(registro: dict) -> dict:
    proposicoes = sorted(registro["proposicoes"], key=lambda p: p["data"], reverse=True)
    vistas = set()
    unicas = []
    for p in proposicoes:  # a mesma proposição pode vir de mais de uma consulta
        if p["url"] not in vistas:
            vistas.add(p["url"])
            unicas.append(p)
    autor = [p for p in unicas if p["principal"]]
    por_tipo = defaultdict(int)
    for p in autor:
        por_tipo[p["tipo"]] += 1

    cota = []
    for (casa, ano), categorias in sorted(registro["cota"].items(), key=lambda i: i[0][1], reverse=True):
        cota.append({
            "casa": casa,
            "ano": ano,
            "total": round(sum(categorias.values()), 2),
            "categorias": [
                {"nome": nome, "valor": round(valor, 2)}
                for nome, valor in sorted(categorias.items(), key=lambda i: i[1], reverse=True)
            ],
        })

    return {
        "desde": PRIMEIRO_ANO,
        "mandatos": sorted(registro["mandatos"], key=lambda m: m["inicio"], reverse=True),
        "perfis": registro["perfis"],
        "proposicoes": {
            "autor": len(autor),
            "coautor": len(unicas) - len(autor),
            "por_tipo": [{"tipo": t, "nome": TIPOS[t], "quantidade": por_tipo[t]} for t in TIPOS if por_tipo[t]],
            "recentes": autor[:RECENTES],
        },
        "cota": cota,
        "atuacao_camara": registro["atuacao_camara"],
    }


def main() -> None:
    chave = carregar_chave()
    pasta_pessoas = PASTA_SAIDA / "pessoas"
    arquivos = {f.stem: f for f in pasta_pessoas.glob("*.json")}
    if not arquivos:
        raise SystemExit("Nenhuma pessoa em pipeline/saida. Rode antes: python pipeline/gerar_pessoas.py")
    pessoas = [json.loads(f.read_text(encoding="utf-8")) for f in arquivos.values()]

    registros: dict[str, dict] = {}
    camara(chave, set(arquivos), registros)
    senado(pessoas, registros)

    for pessoa in pessoas:
        if pessoa["id"] in registros:
            pessoa["parlamento"] = finalizar(registros[pessoa["id"]])
        else:
            pessoa.pop("parlamento", None)
        arquivos[pessoa["id"]].write_text(json.dumps(pessoa, ensure_ascii=False, indent=1), encoding="utf-8")

    com_proposicoes = sum(1 for r in registros.values() if r["proposicoes"])
    com_cota = sum(1 for r in registros.values() if r["cota"])
    print(f"\nParlamento: {len(registros)} pessoas com mandato desde {PRIMEIRO_ANO}, "
          f"{com_proposicoes} com proposições, {com_cota} com gastos de cota")


if __name__ == "__main__":
    main()
