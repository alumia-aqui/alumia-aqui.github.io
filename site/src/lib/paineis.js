// Dados dos Painéis, calculados na geração do site.
// Candidatos: a partir dos Retratos (eleição atual). Congresso: pipeline/gerar_congresso.py.

import fs from "node:fs";
import path from "node:path";
import { carregarPessoas, anoAtual } from "./dados.js";
import { primeiraMaiuscula, minusculo, nomeProprio, nomeUf } from "./texto.js";

const PASTA =
  process.env.ALUMIA_DADOS ?? path.resolve(process.cwd(), "../pipeline/saida");

// Ordens fixas: hierarquia de cargos e níveis de escolaridade, não quantidade.
const ORDEM_CARGOS = [
  "PRESIDENTE", "VICE-PRESIDENTE", "GOVERNADOR", "VICE-GOVERNADOR", "SENADOR",
  "1º SUPLENTE", "2º SUPLENTE", "DEPUTADO FEDERAL", "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL",
  "PREFEITO", "VICE-PREFEITO", "VEREADOR",
];
const ORDEM_ESCOLARIDADE = [
  "ANALFABETO", "LÊ E ESCREVE", "ENSINO FUNDAMENTAL INCOMPLETO", "ENSINO FUNDAMENTAL COMPLETO",
  "ENSINO MÉDIO INCOMPLETO", "ENSINO MÉDIO COMPLETO", "SUPERIOR INCOMPLETO", "SUPERIOR COMPLETO",
];
export const FAIXAS_BENS = [
  "Não declarou bens",
  "Até R$ 100 mil",
  "De R$ 100 mil a R$ 1 milhão",
  "De R$ 1 milhão a R$ 10 milhões",
  "Mais de R$ 10 milhões",
];
const DISPUTOU = ["Primeira eleição desde 2014", "Já disputou outra eleição desde 2014"];

function faixaBens(c) {
  const total = c.bens?.length ? c.total_bens ?? 0 : 0;
  if (!c.bens?.length || total <= 0) return 0;
  if (total <= 100_000) return 1;
  if (total <= 1_000_000) return 2;
  if (total <= 10_000_000) return 3;
  return 4;
}

function posicao(ordem, valor) {
  const i = ordem.indexOf(valor);
  return i === -1 ? ordem.length : i;
}

// Dicionário de valores: guarda o índice de cada valor e devolve a lista ordenada.
function dicionario(ordenar) {
  const valores = new Map();
  return {
    indice(valor) {
      if (!valores.has(valor)) valores.set(valor, valores.size);
      return valores.get(valor);
    },
    // Reordena e devolve [lista, mapa de índice antigo -> novo].
    fechar() {
      const lista = [...valores.keys()].sort(ordenar);
      const novo = new Map(lista.map((v, i) => [valores.get(v), i]));
      return [lista, novo];
    },
  };
}

const alfabetica = (a, b) => (a ?? "").localeCompare(b ?? "", "pt-BR");

let cacheCandidatos = null;

export function painelCandidatos() {
  if (cacheCandidatos) return cacheCandidatos;
  const pessoas = carregarPessoas();
  const ano = anoAtual(pessoas);
  const dims = {
    cargo: dicionario((a, b) => posicao(ORDEM_CARGOS, a) - posicao(ORDEM_CARGOS, b) || alfabetica(a, b)),
    uf: dicionario((a, b) => (a === "BR" ? -1 : b === "BR" ? 1 : alfabetica(nomeUf(a), nomeUf(b)))),
    partido: dicionario(alfabetica),
    escolaridade: dicionario((a, b) => posicao(ORDEM_ESCOLARIDADE, a) - posicao(ORDEM_ESCOLARIDADE, b) || alfabetica(a, b)),
    situacao: dicionario(alfabetica),
  };

  const brutas = []; // uma por candidatura da eleição atual
  for (const p of pessoas) {
    const anteriores = p.candidaturas.some((c) => c.ano !== ano);
    for (const c of p.candidaturas.filter((c) => c.ano === ano)) {
      brutas.push({
        id: p.id,
        nome: nomeProprio(c.nome_social || c.nome_urna || p.nome),
        numero: c.numero,
        uf: c.uf,
        v: [
          dims.cargo.indice(c.cargo || "Não informado"),
          dims.uf.indice(c.uf || "Não informado"),
          dims.partido.indice(c.partido?.sigla || "Sem partido"),
          dims.escolaridade.indice(c.escolaridade || "Não informada"),
          faixaBens(c),
          dims.situacao.indice(c.situacao_candidatura || "Não informada"),
          anteriores ? 1 : 0,
        ],
      });
    }
  }

  const fechados = Object.fromEntries(Object.entries(dims).map(([k, d]) => [k, d.fechar()]));
  const ordemDims = ["cargo", "uf", "partido", "escolaridade", null, "situacao", null];
  for (const b of brutas) {
    b.v = b.v.map((x, i) => (ordemDims[i] ? fechados[ordemDims[i]][1].get(x) : x));
  }

  // Cubo: combinações de valores com a quantidade de candidaturas.
  const contagem = new Map();
  for (const b of brutas) {
    const chave = b.v.join(",");
    contagem.set(chave, (contagem.get(chave) ?? 0) + 1);
  }
  const linhas = [...contagem].map(([chave, n]) => [...chave.split(",").map(Number), n]);

  const rotulo = (texto) => primeiraMaiuscula(minusculo(texto));
  const listas = {
    cargo: fechados.cargo[0].map(rotulo),
    uf: fechados.uf[0].map((u) => (u === "BR" ? "Brasil (presidência)" : nomeUf(u))),
    ufSigla: fechados.uf[0],
    partido: fechados.partido[0],
    escolaridade: fechados.escolaridade[0].map(rotulo),
    bens: FAIXAS_BENS,
    situacao: fechados.situacao[0].map(rotulo),
    disputou: DISPUTOU,
  };

  // Nomes por estado, em ordem alfabética, para a lista abaixo dos gráficos.
  const porUf = new Map();
  for (const b of brutas) {
    if (!porUf.has(b.uf)) porUf.set(b.uf, []);
    porUf.get(b.uf).push([b.id, b.nome, b.numero ?? "", ...b.v]);
  }
  for (const lista of porUf.values()) lista.sort((a, b) => alfabetica(a[1], b[1]));

  cacheCandidatos = { ano, total: brutas.length, listas, linhas, porUf };
  return cacheCandidatos;
}

export function painelCongresso() {
  const arquivo = path.join(PASTA, "congresso.json");
  if (!fs.existsSync(arquivo)) return null;
  return JSON.parse(fs.readFileSync(arquivo, "utf-8"));
}
