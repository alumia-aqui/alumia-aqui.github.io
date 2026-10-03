"""Junta aos Retratos as sanções registradas nos cadastros da CGU.

Cadastros (Portal da Transparência, atualizados todo dia):
- CEIS: pessoas e empresas punidas ou proibidas de contratar com o poder
  público. Inclui as condenações por improbidade administrativa que o CNJ envia.
- CNEP: punições com base na Lei Anticorrupção (Lei 12.846/2013).
- CEAF: servidores federais expulsos (demissão, cassação de aposentadoria...).

Ligação com as pessoas candidatas:
- CEIS e CNEP publicam o CPF completo da pessoa física: ligação pelo CPF.
- CEAF publica o CPF mascarado (***.123.456-**): a ligação exige os 6 dígitos
  do meio iguais e o nome completo idêntico ao registrado no TSE.

O CPF dos candidatos vem do arquivo do TSE já baixado por gerar_pessoas.py e
fica só na memória. Rodar depois de gerar_pessoas.py:
    python pipeline/gerar_sancoes.py
"""

import csv
import io
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta

import tse
from gerar_pessoas import PASTA_SAIDA, carregar_chave, codigo_pessoa

PASTA = tse.PASTA_DADOS / "sancoes"
CADASTROS = {
    "ceis": "CEIS - Cadastro de Empresas Inidôneas e Suspensas",
    "cnep": "CNEP - Cadastro Nacional de Empresas Punidas",
    "ceaf": "CEAF - Cadastro de Expulsões da Administração Federal",
}
# Leis citadas com frequência, para explicar em linguagem simples.
LEIS = {
    "8429": "Lei de Improbidade Administrativa",
    "12846": "Lei Anticorrupção",
    "8666": "antiga Lei de Licitações",
    "14133": "Lei de Licitações",
    "10520": "Lei do Pregão",
    "8112": "Estatuto dos Servidores Públicos Federais",
    "9504": "Lei das Eleições",
}


def normalizar(texto: str | None) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^A-Za-z ]", " ", texto).upper().split())


def baixar_cadastro(cadastro: str) -> bytes:
    """Arquivo mais recente publicado (o do dia ainda pode não existir)."""
    PASTA.mkdir(parents=True, exist_ok=True)
    destino = PASTA / f"{cadastro}.zip"
    if destino.exists() and time.time() - destino.stat().st_mtime < 86400:
        return destino.read_bytes()
    for dias in range(0, 10):
        dia = (date.today() - timedelta(days=dias)).strftime("%Y%m%d")
        url = f"https://portaldatransparencia.gov.br/download-de-dados/{cadastro}/{dia}"
        pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (alumia-aqui; dados abertos)"})
        try:
            with urllib.request.urlopen(pedido, timeout=180) as resposta:
                dados = resposta.read()
        except urllib.error.HTTPError:
            continue
        if dados[:2] == b"PK":
            print(f"  {cadastro.upper()}: arquivo de {dia[6:]}/{dia[4:6]}/{dia[:4]}")
            destino.write_bytes(dados)
            return dados
    if destino.exists():
        print(f"  {cadastro.upper()}: sem arquivo novo; usando o último baixado")
        return destino.read_bytes()
    raise RuntimeError(f"Não foi possível baixar o {cadastro.upper()}")


def linhas_cadastro(dados: bytes):
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        bruto = z.read(z.namelist()[0])
    try:
        texto = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")
    # Os nomes de coluna variam um pouco entre cadastros (espaço duplo, por exemplo).
    for linha in csv.DictReader(io.StringIO(texto), delimiter=";"):
        yield {" ".join(k.split()): (v or "").strip() for k, v in linha.items() if k}


def data_iso(texto: str) -> str | None:
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def resumir_fundamento(texto: str) -> str | None:
    """'LEI 8429 - ART. 12 - INDEPENDENTEMENTE...' -> 'Lei 8429, art. 12 (Lei de Improbidade Administrativa)'."""
    if not texto:
        return None
    primeiro = texto.split(";;")[0]
    partes = [p.strip() for p in primeiro.split(" - ")]
    lei = re.match(r"LEI\s+N?[º°.]?\s*([\d.]+)", partes[0], re.I)
    if lei:
        numero = lei.group(1).replace(".", "")
        resumo = f"Lei {numero}"
        if len(partes) > 1 and re.match(r"ART", partes[1], re.I):
            resumo += ", " + partes[1].lower().replace("art.", "art.")
        return f"{resumo} ({LEIS[numero]})" if numero in LEIS else resumo
    return partes[0][:120].capitalize()


def main() -> None:
    chave = carregar_chave()
    pasta_pessoas = PASTA_SAIDA / "pessoas"
    arquivos = {f.stem: f for f in pasta_pessoas.glob("*.json")}
    if not arquivos:
        raise SystemExit("Nenhuma pessoa em pipeline/saida. Rode antes: python pipeline/gerar_pessoas.py")
    pessoas = {id_: json.loads(f.read_text(encoding="utf-8")) for id_, f in arquivos.items()}
    ano = max(c["ano"] for p in pessoas.values() for c in p["candidaturas"])

    # CPF da eleição atual -> pessoa. Só na memória.
    por_cpf: dict[str, str] = {}
    por_meio_e_nome: dict[tuple[str, str], str] = {}
    for linha in tse.ler_candidatos(ano):
        cpf = tse.limpar(linha.get("NR_CPF_CANDIDATO"))
        if not cpf or not cpf.isdigit():
            continue
        id_pessoa = codigo_pessoa(cpf, chave)
        if id_pessoa in pessoas:
            por_cpf[cpf] = id_pessoa
            por_meio_e_nome[(cpf[3:9], normalizar(linha.get("NM_CANDIDATO")))] = id_pessoa

    print("Sanções (CGU)")
    sancoes: dict[str, list[dict]] = {}
    for cadastro, nome_cadastro in CADASTROS.items():
        ligadas = 0
        for linha in linhas_cadastro(baixar_cadastro(cadastro)):
            if linha.get("TIPO DE PESSOA") != "F":
                continue
            documento = linha.get("CPF OU CNPJ DO SANCIONADO", "")
            digitos = re.sub(r"\D", "", documento)
            if len(digitos) == 11:
                id_pessoa = por_cpf.get(digitos)
            elif re.fullmatch(r"\*{3}\.\d{3}\.\d{3}-\*{2}", documento):
                id_pessoa = por_meio_e_nome.get((digitos, normalizar(linha.get("NOME DO SANCIONADO"))))
            else:
                id_pessoa = None
            if not id_pessoa:
                continue
            ligadas += 1
            fim = data_iso(linha.get("DATA FINAL SANÇÃO", ""))
            sancoes.setdefault(id_pessoa, []).append({
                "cadastro": cadastro.upper(),
                "cadastro_nome": nome_cadastro,
                "codigo": linha.get("CÓDIGO DA SANÇÃO"),
                "categoria": linha.get("CATEGORIA DA SANÇÃO") or None,
                "orgao": linha.get("ÓRGÃO SANCIONADOR") or None,
                "uf_orgao": linha.get("UF ÓRGÃO SANCIONADOR") or None,
                "esfera": linha.get("ESFERA ÓRGÃO SANCIONADOR") or None,
                "processo": linha.get("NÚMERO DO PROCESSO") or None,
                "inicio": data_iso(linha.get("DATA INÍCIO SANÇÃO", "")),
                "fim": fim,
                "transito_julgado": data_iso(linha.get("DATA DO TRÂNSITO EM JULGADO", "")),
                "publicacao": linha.get("PUBLICAÇÃO") if linha.get("PUBLICAÇÃO") not in ("", "Sem Informação") else None,
                "fundamento": resumir_fundamento(linha.get("FUNDAMENTAÇÃO LEGAL", "")),
                "origem": linha.get("ORIGEM INFORMAÇÕES") or None,
                "vigente": fim is None or fim >= date.today().isoformat(),
            })
        print(f"  {cadastro.upper()}: {ligadas} sanções ligadas a candidatos")

    consulta = date.today().isoformat()
    for id_pessoa, pessoa in pessoas.items():
        lista = sorted(sancoes.get(id_pessoa, []), key=lambda s: s["inicio"] or "", reverse=True)
        pessoa["sancoes"] = {"consultado_em": consulta, "cadastros": list(CADASTROS), "registros": lista}
        arquivos[id_pessoa].write_text(json.dumps(pessoa, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {len(sancoes)} pessoas candidatas com ao menos uma sanção registrada")


if __name__ == "__main__":
    main()
