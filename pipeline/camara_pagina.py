"""Leitura da página de um deputado no site da Câmara.

Presença, salário, imóvel funcional, auxílio-moradia, verba e pessoal de
gabinete e viagens em missão oficial não estão nos dados abertos da Câmara.
Aparecem só na página https://www.camara.leg.br/deputados/<id>?ano=<ano>.

Se a Câmara mudar o layout da página, a leitura devolve campos vazios em vez
de valores errados. O Retrato só mostra o que foi lido.

Teste:  python pipeline/camara_pagina.py 204534 2026
"""

import html as html_lib
import re
import sys
import urllib.request


def texto(fragmento: str) -> str:
    """Tira as tags e junta os espaços."""
    sem_tags = re.sub(r"<[^>]+>", " ", fragmento)
    return " ".join(html_lib.unescape(sem_tags).split())


def inteiro(valor: str | None) -> int | None:
    achado = re.search(r"\d+", valor or "")
    return int(achado.group(0)) if achado else None


def reais(valor: str | None) -> float | None:
    achado = re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", valor or "")
    if not achado:
        return None
    return float(achado.group(0).replace(".", "").replace(",", "."))


def beneficios(pagina: str) -> dict[str, str]:
    """Blocos "beneficio": título -> texto exibido (ex.: "Imóvel funcional" -> "Faz uso desde ...").

    Cada bloco é lido só até o início do próximo, para um bloco com layout
    diferente nunca pegar o valor do vizinho.
    """
    inicios = [m.start() for m in re.finditer(r'class="beneficio__titulo"', pagina)]
    resultado = {}
    for i, inicio in enumerate(inicios):
        fim = inicios[i + 1] if i + 1 < len(inicios) else inicio + 4000
        fim_item = pagina.find("</li>", inicio)
        if 0 <= fim_item < fim:
            fim = fim_item
        bloco = pagina[inicio:fim]
        titulo = re.match(r'class="beneficio__titulo">\s*([^<]*)', bloco)
        valor = re.search(
            r'</h3>\s*<(?:a|span)[^>]*class="beneficio__info[^"]*"[^>]*>(.*?)</(?:a|span)>', bloco, re.DOTALL
        )
        if titulo and valor:
            resultado.setdefault(texto(titulo.group(1)), texto(valor.group(1)))
    return resultado


def presenca(pagina: str, titulo: str) -> dict | None:
    """Presenças e ausências da seção "Presença em Plenário" ou "Presença em comissões"."""
    inicio = pagina.find(f'data-original-title="{titulo}"')
    if inicio < 0:
        return None
    # Vai até a próxima seção de presença (o HTML real tem muita indentação entre as tags).
    proxima = pagina.find('data-original-title="Presença', inicio + 10)
    trecho = pagina[inicio : proxima if proxima > 0 else inicio + 20000]
    pares = re.findall(
        r'class="presencas__label">(.*?)</span>\s*<span\s+class="presencas__qtd">\s*(.*?)\s*</span>',
        trecho,
        re.DOTALL,
    )
    valores = {}
    for rotulo, quantidade in pares[:3]:
        rotulo = texto(rotulo).lower()
        if rotulo.startswith("presença"):
            valores["presencas"] = inteiro(quantidade)
        elif "não justificada" in rotulo:
            valores["ausencias_nao_justificadas"] = inteiro(quantidade)
        elif "justificada" in rotulo:
            valores["ausencias_justificadas"] = inteiro(quantidade)
    return valores if len(valores) == 3 else None


def verba_gabinete(pagina: str) -> dict | None:
    inicio = pagina.find('id="percentualgastoverbagabinete"')
    if inicio < 0:
        return None
    tabela = pagina[inicio : pagina.find("</table>", inicio)]
    for linha in re.findall(r"<tr>(.*?)</tr>", tabela, re.DOTALL):
        celulas = [texto(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", linha, re.DOTALL)]
        if len(celulas) >= 3 and celulas[0].lower().startswith("gast"):
            percentual = re.search(r"\d+(?:[.,]\d+)?", celulas[2])
            return {
                "gasto": reais(celulas[1]),
                "percentual": float(percentual.group(0).replace(",", ".")) if percentual else None,
            }
    return None


def ler(pagina: str) -> dict:
    b = beneficios(pagina)
    pessoal = b.get("Pessoal de gabinete")
    return {
        "presenca_plenario": presenca(pagina, "Presença em Plenário"),
        "presenca_comissoes": presenca(pagina, "Presença em comissões"),
        "salario_bruto": reais(b.get("Salário mensal bruto")),
        "imovel_funcional": b.get("Imóvel funcional") or None,
        "auxilio_moradia": b.get("Auxílio-moradia") or None,
        "viagens_missao_oficial": inteiro(b.get("Viagens em missão oficial")),
        "pessoal_gabinete": pessoal or None,
        "verba_gabinete": verba_gabinete(pagina),
    }


def baixar(id_deputado: str, ano: int) -> str:
    url = f"https://www.camara.leg.br/deputados/{id_deputado}?ano={ano}"
    pedido = urllib.request.Request(url, headers={"User-Agent": "alumia-aqui (dados abertos)"})
    with urllib.request.urlopen(pedido, timeout=120) as resposta:
        return resposta.read().decode("utf-8", "replace")


if __name__ == "__main__":
    import json

    ids = sys.argv[1].split(",") if len(sys.argv) > 1 else ["204534"]
    anos = [int(a) for a in sys.argv[2:]] or [2026]
    for id_deputado in ids:
        for ano in anos:
            print(id_deputado, ano, json.dumps(ler(baixar(id_deputado, ano)), ensure_ascii=False))
