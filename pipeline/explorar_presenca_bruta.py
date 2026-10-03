"""Mostra o HTML bruto (sem limpeza) da seção de presença da página de um deputado."""

import sys

sys.path.insert(0, "pipeline")
import camara_pagina

pagina = camara_pagina.baixar(sys.argv[1] if len(sys.argv) > 1 else "204534", 2026)
for termo in ("Presença em Plenário", "presencas__label"):
    i = pagina.find(termo)
    print(f"\n=== {termo!r} em {i}")
    print(repr(pagina[max(0, i - 400) : i + 1800]))
