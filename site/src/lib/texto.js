// Conversão dos textos do TSE (em maiúsculas e siglas) para linguagem simples.

const MINUSCULAS = new Set(["da", "de", "do", "das", "dos", "e", "di", "du"]);

// "JOSÉ DA SILVA" -> "José da Silva"
export function nomeProprio(texto) {
  if (!texto) return "";
  return texto
    .toLowerCase()
    .split(/\s+/)
    .map((palavra, i) =>
      i > 0 && MINUSCULAS.has(palavra)
        ? palavra
        : palavra.replace(/(^|[-'])(\p{L})/gu, (m, sep, letra) => sep + letra.toUpperCase())
    )
    .join(" ");
}

// "DEPUTADO FEDERAL" -> "deputado federal"
export function minusculo(texto) {
  return texto ? texto.toLowerCase() : "";
}

export function primeiraMaiuscula(texto) {
  return texto ? texto.charAt(0).toUpperCase() + texto.slice(1) : "";
}

const UFS = {
  AC: "Acre", AL: "Alagoas", AP: "Amapá", AM: "Amazonas", BA: "Bahia", CE: "Ceará",
  DF: "Distrito Federal", ES: "Espírito Santo", GO: "Goiás", MA: "Maranhão",
  MT: "Mato Grosso", MS: "Mato Grosso do Sul", MG: "Minas Gerais", PA: "Pará",
  PB: "Paraíba", PR: "Paraná", PE: "Pernambuco", PI: "Piauí", RJ: "Rio de Janeiro",
  RN: "Rio Grande do Norte", RS: "Rio Grande do Sul", RO: "Rondônia", RR: "Roraima",
  SC: "Santa Catarina", SP: "São Paulo", SE: "Sergipe", TO: "Tocantins", BR: "Brasil",
};

export function nomeUf(sigla) {
  return UFS[sigla] ?? sigla ?? "";
}

// Onde a candidatura acontece: estado, município ou o país todo.
export function localCandidatura(c) {
  if (c.uf === "BR") return "no Brasil";
  if (c.local && c.local.toUpperCase() !== nomeUf(c.uf).toUpperCase()) {
    return `em ${nomeProprio(c.local)} (${c.uf})`;
  }
  return `em ${nomeUf(c.uf)}`;
}

// Frases neutras em gênero: os dados não informam como cada pessoa se identifica.
const RESULTADOS = {
  "ELEITO": "Conquistou a vaga",
  "ELEITO POR QP": "Conquistou a vaga pelo quociente partidário",
  "ELEITO POR MÉDIA": "Conquistou a vaga por média",
  "ELEITO POR MEDIA": "Conquistou a vaga por média",
  "SUPLENTE": "Ficou na suplência",
  "NÃO ELEITO": "Não conquistou a vaga",
  "NAO ELEITO": "Não conquistou a vaga",
  "2º TURNO": "Foi para o segundo turno",
};

export function resultado(texto) {
  if (!texto) return null;
  return RESULTADOS[texto.toUpperCase()] ?? primeiraMaiuscula(minusculo(texto));
}

const SITUACOES = {
  APTO: "Candidatura apta: pôde concorrer",
  INAPTO: "Candidatura inapta: não seguiu na disputa",
};

export function situacao(texto) {
  if (!texto) return null;
  return SITUACOES[texto.toUpperCase()] ?? primeiraMaiuscula(minusculo(texto));
}

// "01/02/1970" -> idade em anos na data de hoje
export function idade(dataNascimento) {
  if (!dataNascimento) return null;
  const [dia, mes, ano] = dataNascimento.split("/").map(Number);
  if (!ano) return null;
  const hoje = new Date();
  let anos = hoje.getFullYear() - ano;
  if (hoje.getMonth() + 1 < mes || (hoje.getMonth() + 1 === mes && hoje.getDate() < dia)) anos--;
  return anos;
}

export function nomeExibido(c, pessoa) {
  return nomeProprio(c?.nome_social || c?.nome_urna || pessoa.nome);
}

const REAIS = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export function reais(valor) {
  return valor == null ? "" : REAIS.format(valor);
}

// Soma os bens por tipo: "Casa" R$ 300 mil, "Veículo" R$ 50 mil...
export function bensPorTipo(bens) {
  const somas = new Map();
  for (const bem of bens ?? []) {
    const tipo = primeiraMaiuscula(minusculo(bem.tipo || "Outros"));
    const atual = somas.get(tipo) ?? { tipo, valor: 0, quantidade: 0 };
    atual.valor += bem.valor ?? 0;
    atual.quantidade += 1;
    somas.set(tipo, atual);
  }
  return [...somas.values()].sort((a, b) => b.valor - a.valor);
}
