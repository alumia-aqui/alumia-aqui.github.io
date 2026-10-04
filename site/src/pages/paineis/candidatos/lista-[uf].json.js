// Lista de candidaturas de um estado, carregada pelo painel quando o estado é escolhido.
// Cada linha: [código do Retrato, nome, número, cargo, uf, partido, escolaridade, faixa de bens, situação, disputou antes].
import { painelCandidatos } from "../../../lib/paineis.js";

export function getStaticPaths() {
  return [...painelCandidatos().porUf.keys()].map((uf) => ({ params: { uf: uf.toLowerCase() } }));
}

export function GET({ params }) {
  const lista = painelCandidatos().porUf.get(params.uf.toUpperCase()) ?? [];
  return new Response(JSON.stringify(lista), { headers: { "Content-Type": "application/json" } });
}
