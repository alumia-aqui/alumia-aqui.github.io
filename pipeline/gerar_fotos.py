"""Baixa as fotos dos candidatos da eleição atual e gera versões pequenas para o site.

A foto é a mesma que o candidato entregou ao TSE e que aparece na urna. Uso
restrito ao Retrato e à busca, para o eleitor confirmar a pessoa certa. Fotos
de eleições anteriores não são guardadas.

Cada foto vira um JPEG de até 180x240 pixels em site/public/fotos/<id>.jpg.
JPEG, e não WebP, porque o WhatsApp nem sempre mostra WebP na prévia do link.

Depende do Pillow:  pip install pillow
Rodar depois de gerar_pessoas.py:  python pipeline/gerar_fotos.py
"""

import io
import json
import re
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageOps

import tse

URL_FOTOS = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes{ano}/fotos/foto_cand{ano}_{uf}_div.zip"
PASTA_FOTOS_BRUTAS = tse.PASTA_DADOS / "fotos"
PASTA_SAIDA = Path(__file__).parent / "saida"
PASTA_SITE = Path(__file__).parent.parent / "site" / "public" / "fotos"
TAMANHO = (180, 240)


def baixar_zip(ano: int, uf: str) -> Path | None:
    destino = PASTA_FOTOS_BRUTAS / f"foto_cand{ano}_{uf}_div.zip"
    if destino.exists():
        return destino
    PASTA_FOTOS_BRUTAS.mkdir(parents=True, exist_ok=True)
    url = URL_FOTOS.format(ano=ano, uf=uf)
    try:
        return tse.baixar_url(url, destino)
    except tse.ArquivoInexistente:
        print(f"  Fotos de {uf}: arquivo não encontrado ({url})")
        return None


def reduzir(dados: bytes, destino: Path) -> None:
    with Image.open(io.BytesIO(dados)) as imagem:
        imagem = ImageOps.exif_transpose(imagem).convert("RGB")
        imagem = ImageOps.fit(imagem, TAMANHO, method=Image.Resampling.LANCZOS, centering=(0.5, 0.35))
        imagem.save(destino, "JPEG", quality=72, optimize=True, progressive=True)


def main() -> None:
    pessoas = [json.loads(f.read_text(encoding="utf-8")) for f in (PASTA_SAIDA / "pessoas").glob("*.json")]
    if not pessoas:
        sys.exit("Nenhuma pessoa em pipeline/saida. Rode antes: python pipeline/gerar_pessoas.py")
    ano = max(c["ano"] for p in pessoas for c in p["candidaturas"])

    # SQ_CANDIDATO de cada candidatura atual -> pessoa. Inclui registros repetidos unidos.
    por_sq: dict[str, str] = {}
    ufs: set[str] = set()
    for pessoa in pessoas:
        for c in pessoa["candidaturas"]:
            if c["ano"] != ano:
                continue
            for sq in c.get("registros_tse") or [c["sq_candidato"]]:
                por_sq[sq] = pessoa["id"]
            ufs.add(c["uf"])

    PASTA_SITE.mkdir(parents=True, exist_ok=True)
    for antiga in PASTA_SITE.glob("*.jpg"):
        antiga.unlink()

    com_foto: set[str] = set()
    for uf in sorted(ufs):
        caminho = baixar_zip(ano, uf)
        if caminho is None:
            continue
        with zipfile.ZipFile(caminho) as z:
            for nome in z.namelist():
                # Ex.: FSC240001647892_div.jpg -> F + UF + SQ_CANDIDATO.
                achado = re.match(r"F[A-Z]{2}(\d+)", Path(nome).stem.upper()) or re.search(
                    r"(\d+)", Path(nome).stem
                )
                if not achado:
                    continue
                id_pessoa = por_sq.get(achado.group(1))
                if id_pessoa is None or id_pessoa in com_foto:
                    continue
                try:
                    reduzir(z.read(nome), PASTA_SITE / f"{id_pessoa}.jpg")
                    com_foto.add(id_pessoa)
                except Exception as erro:  # foto corrompida não interrompe as demais
                    print(f"  Foto ignorada ({nome}): {erro}")

    total = sum(f.stat().st_size for f in PASTA_SITE.glob("*.jpg"))
    print(f"Fotos: {len(com_foto)} de {len(pessoas)} pessoas, {total / 1e6:.1f} MB em {PASTA_SITE}")


if __name__ == "__main__":
    main()
