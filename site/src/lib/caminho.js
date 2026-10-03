// Monta endereços internos respeitando a base do site.
// No GitHub Pages o site fica em /alumia-aqui/; com domínio próprio, em /.
const BASE = import.meta.env.BASE_URL.replace(/\/?$/, "/");

export function caminho(destino = "") {
  return BASE + destino.replace(/^\//, "");
}
