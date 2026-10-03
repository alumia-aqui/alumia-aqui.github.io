import { defineConfig } from "astro/config";

// ALUMIA_SITE e ALUMIA_BASE vêm do processo de publicação (GitHub Actions).
// Sem elas, o site é gerado para a raiz, como no domínio próprio.
export default defineConfig({
  site: process.env.ALUMIA_SITE ?? "https://alumiaaqui.com.br",
  base: process.env.ALUMIA_BASE ?? "/",
  build: { format: "directory" },
});
