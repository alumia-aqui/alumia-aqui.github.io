"""Gera um arquivo JSON por pessoa candidata na eleição mais recente.

Regras do modelo:
- Candidatura: um SQ_CANDIDATO, com um ou dois turnos.
- Pessoa: todas as candidaturas com o mesmo CPF, em qualquer eleição. Nos anos
  sem CPF nos dados abertos (ex.: 2024), a ligação usa o título de eleitor
  junto com a data de nascimento.
- Candidaturas inaptas entram no histórico, com a situação informada.
- Registro repetido: o TSE às vezes tem dois SQ_CANDIDATO para a mesma
  candidatura (mesma pessoa, ano, cargo, local e número). Ficam unidos em um,
  e os códigos de todos os registros ficam em registros_tse.
- Bens: os declarados em cada candidatura, com tipo e valor. A descrição do
  bem fica de fora, porque costuma trazer endereço e número de conta.

O CPF é usado só aqui, para ligar os registros. Nos arquivos gerados, cada
pessoa recebe um código derivado do CPF com uma chave secreta (HMAC). Sem a
chave, não dá para voltar do código ao CPF.

A chave fica na variável de ambiente ALUMIA_CHAVE ou no arquivo .env na raiz
do repositório. Se não existir, o script cria uma. Perder a chave muda o
código de todas as pessoas (e os endereços das páginas), então guarde uma cópia.

Uso:
    python pipeline/gerar_pessoas.py
    python pipeline/gerar_pessoas.py 2026 2022 2018   (escolher os anos; o primeiro é a eleição atual)
"""

import hashlib
import hmac
import json
import os
import secrets
import sys
from pathlib import Path

from tse import ArquivoInexistente, baixar, ler_bens, ler_candidatos, limpar, valor_em_reais

RAIZ = Path(__file__).parent.parent
ARQUIVO_CHAVE = RAIZ / ".env"
PASTA_SAIDA = Path(__file__).parent / "saida"

# Eleição atual primeiro; as demais formam o histórico.
ANOS_PADRAO = [2026, 2024, 2022, 2020, 2018, 2016, 2014]

# Campos que nunca saem do pipeline: CPF, título de eleitor e e-mail.
# Cor/raça, gênero e estado civil também ficam de fora: não dizem nada sobre a
# conduta pública da pessoa.


def carregar_chave() -> bytes:
    chave = os.environ.get("ALUMIA_CHAVE")
    if not chave and ARQUIVO_CHAVE.exists():
        for linha in ARQUIVO_CHAVE.read_text(encoding="utf-8").splitlines():
            if linha.startswith("ALUMIA_CHAVE="):
                chave = linha.split("=", 1)[1].strip()
    if not chave and os.environ.get("CI"):
        # Na publicação automática, criar uma chave nova mudaria o endereço de todas as páginas.
        sys.exit("ALUMIA_CHAVE não configurada. Cadastre a chave nos segredos do repositório.")
    if not chave:
        chave = secrets.token_hex(32)
        with open(ARQUIVO_CHAVE, "a", encoding="utf-8") as arquivo:
            arquivo.write(f"ALUMIA_CHAVE={chave}\n")
        print(f"Chave nova criada em {ARQUIVO_CHAVE}. Guarde uma cópia em lugar seguro.")
    return chave.encode()


def codigo_pessoa(cpf: str, chave: bytes) -> str:
    return hmac.new(chave, cpf.encode(), hashlib.sha256).hexdigest()[:16]


def cpf_valido(linha: dict) -> str | None:
    cpf = limpar(linha.get("NR_CPF_CANDIDATO"))
    return cpf if cpf and cpf.isdigit() else None


def montar_candidatura(linha: dict) -> dict:
    return {
        "ano": int(linha["ANO_ELEICAO"]),
        "eleicao": limpar(linha.get("DS_ELEICAO")),
        "sq_candidato": limpar(linha.get("SQ_CANDIDATO")),
        "cargo": limpar(linha.get("DS_CARGO")),
        "uf": limpar(linha.get("SG_UF")),
        "local": limpar(linha.get("NM_UE")),
        "numero": limpar(linha.get("NR_CANDIDATO")),
        "nome_urna": limpar(linha.get("NM_URNA_CANDIDATO")),
        "nome_social": limpar(linha.get("NM_SOCIAL_CANDIDATO")),
        "partido": {
            "sigla": limpar(linha.get("SG_PARTIDO")),
            "nome": limpar(linha.get("NM_PARTIDO")),
            "numero": limpar(linha.get("NR_PARTIDO")),
        },
        "federacao": limpar(linha.get("NM_FEDERACAO")),
        "coligacao": limpar(linha.get("NM_COLIGACAO")),
        "situacao_candidatura": limpar(linha.get("DS_SITUACAO_CANDIDATURA")),
        "escolaridade": limpar(linha.get("DS_GRAU_INSTRUCAO")),
        "ocupacao": limpar(linha.get("DS_OCUPACAO")),
        "turnos": [],
    }


def adicionar_linha(pessoa: dict, linha: dict) -> None:
    """Junta a linha na candidatura certa (mesmo SQ_CANDIDATO = outro turno)."""
    sq = limpar(linha.get("SQ_CANDIDATO"))
    candidatura = next((c for c in pessoa["candidaturas"] if c["sq_candidato"] == sq), None)
    if candidatura is None:
        candidatura = montar_candidatura(linha)
        pessoa["candidaturas"].append(candidatura)
    candidatura["turnos"].append({
        "turno": limpar(linha.get("NR_TURNO")),
        "data": limpar(linha.get("DT_ELEICAO")),
        "resultado": limpar(linha.get("DS_SIT_TOT_TURNO")),
    })


def adicionar_bens(pessoas: dict[str, dict], anos: list[int]) -> None:
    """Junta os bens a cada candidatura, pelo ano e pelo SQ_CANDIDATO.

    bens = None: o arquivo do ano não foi lido (não se sabe).
    bens = []: o arquivo foi lido e não há bens declarados nessa candidatura.
    """
    candidaturas = {}
    for pessoa in pessoas.values():
        for c in pessoa["candidaturas"]:
            c["bens"] = None
            c["total_bens"] = None
            candidaturas[(c["ano"], c["sq_candidato"])] = c

    for ano in anos:
        try:
            baixar("bem_candidato", ano)
        except ArquivoInexistente:
            print(f"Bens {ano}: arquivo não publicado pelo TSE")
            continue

        do_ano = {sq: c for (a, sq), c in candidaturas.items() if a == ano}
        colunas_ok = None
        com_bens = set()
        for linha in ler_bens(ano):
            if colunas_ok is None:
                faltando = {"SQ_CANDIDATO", "VR_BEM_CANDIDATO"} - set(linha)
                colunas_ok = not faltando
                if faltando:
                    print(f"Bens {ano}: colunas esperadas não encontradas {faltando}.")
                    print(f"  Colunas do arquivo: {', '.join(linha)}")
                    break
            sq = limpar(linha.get("SQ_CANDIDATO"))
            c = do_ano.get(sq)
            if c is None:
                continue
            if c["bens"] is None:
                c["bens"] = []
            c["bens"].append({
                "tipo": limpar(linha.get("DS_TIPO_BEM_CANDIDATO")),
                "valor": valor_em_reais(linha.get("VR_BEM_CANDIDATO")),
            })
            com_bens.add(sq)

        if colunas_ok is False:
            continue
        # Arquivo lido por inteiro: quem não aparece nele não declarou bens.
        for c in do_ano.values():
            if c["bens"] is None:
                c["bens"] = []
        print(f"Bens {ano}: {len(com_bens)} candidaturas com bens declarados")

    for c in candidaturas.values():
        if c["bens"] is not None:
            c["bens"].sort(key=lambda b: b["valor"] or 0, reverse=True)
            c["total_bens"] = round(sum(b["valor"] or 0 for b in c["bens"]), 2)


def prioridade(c: dict) -> tuple:
    """Entre registros repetidos, fica o mais completo: apto, com bens, maior total."""
    apto = (c["situacao_candidatura"] or "").upper() == "APTO"
    return (apto, bool(c["bens"]), c["total_bens"] or 0, int(c["sq_candidato"] or 0))


def unir_registros_repetidos(pessoa: dict) -> int:
    grupos: dict[tuple, list[dict]] = {}
    for c in pessoa["candidaturas"]:
        chave = (c["ano"], c["cargo"], c["uf"], c["local"], c["numero"])
        grupos.setdefault(chave, []).append(c)
    unidas = []
    repetidos = 0
    for grupo in grupos.values():
        escolhida = max(grupo, key=prioridade)
        escolhida["registros_tse"] = sorted(c["sq_candidato"] for c in grupo)
        repetidos += len(grupo) - 1
        unidas.append(escolhida)
    pessoa["candidaturas"] = unidas
    return repetidos


def main() -> None:
    anos = [int(a) for a in sys.argv[1:]] or ANOS_PADRAO
    ano_atual, historico = anos[0], anos[1:]
    chave = carregar_chave()

    # 1. Pessoas da eleição atual, indexadas pelo CPF (só em memória).
    pessoas: dict[str, dict] = {}
    titulos: dict[str, str] = {}  # título de eleitor -> CPF
    titulo_do_cpf: dict[str, str] = {}
    sem_cpf = 0
    for linha in ler_candidatos(ano_atual):
        cpf = cpf_valido(linha)
        if not cpf:
            sem_cpf += 1
            continue
        pessoa = pessoas.setdefault(cpf, {
            "id": codigo_pessoa(cpf, chave),
            "nome": limpar(linha.get("NM_CANDIDATO")),
            "data_nascimento": limpar(linha.get("DT_NASCIMENTO")),
            "uf_nascimento": limpar(linha.get("SG_UF_NASCIMENTO")),
            "candidaturas": [],
        })
        adicionar_linha(pessoa, linha)
        titulo = limpar(linha.get("NR_TITULO_ELEITORAL_CANDIDATO"))
        if titulo:
            titulos[titulo] = cpf
            titulo_do_cpf[cpf] = titulo
    print(f"{ano_atual}: {len(pessoas)} pessoas ({sem_cpf} registros sem CPF ficaram de fora)")

    # 2. Histórico: só as linhas de quem é candidato na eleição atual.
    # Liga pelo CPF. Sem CPF (ex.: 2024), liga pelo título de eleitor, desde que
    # a data de nascimento também seja a mesma.
    for ano in historico:
        por_cpf, por_titulo, titulo_divergente = set(), set(), 0
        try:
            baixar("consulta_cand", ano)
        except ArquivoInexistente:
            print(f"{ano}: arquivo de candidatos não publicado pelo TSE")
            continue
        for linha in ler_candidatos(ano):
            cpf = cpf_valido(linha)
            titulo = limpar(linha.get("NR_TITULO_ELEITORAL_CANDIDATO"))
            if cpf:
                if cpf not in pessoas:
                    continue
                if titulo and titulo_do_cpf.get(cpf) and titulo != titulo_do_cpf[cpf]:
                    titulo_divergente += 1
                adicionar_linha(pessoas[cpf], linha)
                por_cpf.add(cpf)
            elif titulo in titulos:
                cpf = titulos[titulo]
                if limpar(linha.get("DT_NASCIMENTO")) != pessoas[cpf]["data_nascimento"]:
                    continue
                adicionar_linha(pessoas[cpf], linha)
                por_titulo.add(cpf)
        resumo = f"{ano}: {len(por_cpf | por_titulo)} pessoas com candidatura nesse ano"
        if por_titulo:
            resumo += f" ({len(por_titulo)} ligadas pelo título de eleitor)"
        if titulo_divergente:
            resumo += f" - {titulo_divergente} registros com mesmo CPF e título diferente"
        print(resumo)

    # 3. Bens declarados em cada candidatura.
    adicionar_bens(pessoas, anos)

    # 4. Saída: um arquivo por pessoa e um índice para a busca.
    pasta_pessoas = PASTA_SAIDA / "pessoas"
    pasta_pessoas.mkdir(parents=True, exist_ok=True)
    # Começa do zero a cada execução, para não sobrar arquivo de rodadas anteriores.
    for antigo in pasta_pessoas.glob("*.json"):
        antigo.unlink()
    repetidos = sum(unir_registros_repetidos(p) for p in pessoas.values())
    if repetidos:
        print(f"Registros repetidos no TSE unidos: {repetidos}")
    indice = []
    for pessoa in pessoas.values():
        pessoa["candidaturas"].sort(key=lambda c: (c["ano"], c["sq_candidato"] or ""), reverse=True)
        caminho = pasta_pessoas / f"{pessoa['id']}.json"
        caminho.write_text(json.dumps(pessoa, ensure_ascii=False, indent=1), encoding="utf-8")

        for c in pessoa["candidaturas"]:
            if c["ano"] == ano_atual:
                indice.append({
                    "id": pessoa["id"],
                    "nome": pessoa["nome"],
                    "nome_urna": c["nome_urna"],
                    "numero": c["numero"],
                    "cargo": c["cargo"],
                    "uf": c["uf"],
                    "partido": c["partido"]["sigla"],
                    "situacao": c["situacao_candidatura"],
                })

    (PASTA_SAIDA / "indice.json").write_text(
        json.dumps(indice, ensure_ascii=False), encoding="utf-8"
    )
    com_historico = sum(1 for p in pessoas.values() if any(c["ano"] != ano_atual for c in p["candidaturas"]))
    print(f"\nArquivos gerados em {PASTA_SAIDA}")
    print(f"  {len(pessoas)} pessoas, {com_historico} com candidaturas em eleições anteriores")
    print(f"  {len(indice)} candidaturas de {ano_atual} no índice de busca")


if __name__ == "__main__":
    main()
