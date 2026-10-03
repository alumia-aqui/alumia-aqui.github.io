// Leitura dos arquivos gerados pelo pipeline (pipeline/gerar_pessoas.py).
// A pasta pode ser trocada pela variável de ambiente ALUMIA_DADOS.

import fs from "node:fs";
import path from "node:path";

const PASTA =
  process.env.ALUMIA_DADOS ?? path.resolve(process.cwd(), "../pipeline/saida");

let cache = null;

export function carregarPessoas() {
  if (cache) return cache;
  const pasta = path.join(PASTA, "pessoas");
  if (!fs.existsSync(pasta)) {
    throw new Error(
      `Dados não encontrados em ${pasta}. Rode antes: python pipeline/gerar_pessoas.py`
    );
  }
  cache = fs
    .readdirSync(pasta)
    .filter((nome) => nome.endsWith(".json"))
    .map((nome) => JSON.parse(fs.readFileSync(path.join(pasta, nome), "utf-8")));
  return cache;
}

export function anoAtual(pessoas) {
  return Math.max(...pessoas.flatMap((p) => p.candidaturas.map((c) => c.ano)));
}

// Fotos geradas por pipeline/gerar_fotos.py em site/public/fotos/<id>.jpg.
const PASTA_FOTOS = path.resolve(process.cwd(), "public/fotos");

export function temFoto(id) {
  return fs.existsSync(path.join(PASTA_FOTOS, `${id}.jpg`));
}
