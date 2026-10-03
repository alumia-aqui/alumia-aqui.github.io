"""Mostra o HTML das seções da página de um deputado no site da Câmara.

Serve para escrever a leitura automática de salário, imóvel funcional,
presença, verba e pessoal de gabinete, que não estão nos dados abertos.

Uso:  python pipeline/explorar_pagina_deputado.py 204534 2026
"""

import re
import sys
import urllib.request

id_deputado = sys.argv[1] if len(sys.argv) > 1 else "204534"
ano = sys.argv[2] if len(sys.argv) > 2 else "2026"


def pagina(url: str) -> str:
    pedido = urllib.request.Request(url, headers={"User-Agent": "alumia-aqui (dados abertos)"})
    with urllib.request.urlopen(pedido, timeout=120) as resposta:
        return resposta.read().decode("utf-8", "replace")


def trecho(html: str, termo: str, antes: int = 300, depois: int = 1600) -> None:
    for achado in list(re.finditer(re.escape(termo), html, re.IGNORECASE))[:2]:
        inicio = max(0, achado.start() - antes)
        bloco = re.sub(r"\s+", " ", html[inicio : achado.end() + depois])
        print(f"\n--- [{termo}] em {achado.start()}\n{bloco}")


html = pagina(f"https://www.camara.leg.br/deputados/{id_deputado}?ano={ano}")
print(f"tamanho da página: {len(html)}")
for termo in (
    "Presença em Plenário", "Presença em Comissões", "Salário mensal", "Imóvel funcional",
    "Auxílio-moradia", "Viagens em missão", "Verba de gabinete", "Pessoal de gabinete",
):
    trecho(html, termo)

print("\n\n===== página de remuneração")
html = pagina(f"https://www.camara.leg.br/deputados/{id_deputado}/remuneracao?ano={ano}")
print(f"tamanho: {len(html)}")
trecho(html, "<table", antes=200, depois=3000)

print("\n\n===== página de presença em plenário")
html = pagina(f"https://www.camara.leg.br/deputados/{id_deputado}/presenca-plenario/{ano}")
trecho(html, "<table", antes=200, depois=1500)
