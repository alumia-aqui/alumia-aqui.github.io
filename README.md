# Alumia Aqui

Site: https://alumia-aqui.github.io/

Site que reúne dados públicos e oficiais sobre candidatos e políticos brasileiros em um relatório simples, com link para cada fonte.

O eleitor digita o nome do candidato, confirma a pessoa certa numa lista com foto e recebe o Retrato: escolaridade, bens declarados, certidões criminais, histórico de candidaturas, contas de campanha e, para quem já teve mandato, projetos de lei, votações e gastos.

## 0 - Princípios

- **Mesmo relatório para todos:** mesmas seções, mesma ordem e mesmas fontes, independente de partido.
- **Sem nota ou ranking:** o site mostra fatos. A avaliação é do eleitor.
- **Fonte oficial em cada informação:** nada aparece sem link para a origem.
- **O bom e o ruim aparecem:** absolvição e arquivamento têm o mesmo destaque que acusação.
- **Linguagem exata:** o relatório informa o estágio do processo (investigado, réu, condenado, absolvido). Sem adjetivos.
- **Identidade confirmada:** só entra no relatório o que estiver ligado à pessoa por identificador forte. Coincidência só de nome fica separada como não confirmada.

## 1 - Estrutura

- **pipeline/** - scripts Python que baixam os dados oficiais e geram um arquivo por candidato.
- **site/** - site estático em Astro. Gera uma página por candidato a partir dos arquivos do pipeline.
- **docs/** - documentação de fontes, modelo de dados e decisões.

## 2 - Como rodar

Pré-requisitos: Python 3.14 e Node.js 24.

- **Gerar os dados:** `python pipeline/gerar_pessoas.py`. Baixa os arquivos do TSE e gera um JSON por pessoa em pipeline/saida/. Na primeira vez cria a chave em .env, que precisa ser guardada.
- **Gerar as fotos:** `pip install pillow` uma vez, depois `python pipeline/gerar_fotos.py`. Opcional: sem fotos, o site funciona normalmente.
- **Painel do Congresso:** `python pipeline/gerar_congresso.py`, depois de gerar_parlamento.py. Gera pipeline/saida/congresso.json com todos os deputados e senadores em exercício, candidatos ou não: partido atual, UF, projetos apresentados na legislatura atual, quantos viraram norma e gasto da cota por ano.
- **Empresas (mensal, no computador local):** `powershell -ExecutionPolicy Bypass -File ferramentas\atualizar_empresas.ps1`. Baixa os dados de sócios da Receita Federal, que recusa conexões vindas do GitHub, gera dados/empresas.json e envia ao repositório. Os arquivos da Receita somam alguns GB; só o mês atual fica guardado.
- **Agendar as empresas:** no PowerShell, dentro da pasta do repositório, rodar uma vez `powershell -ExecutionPolicy Bypass -File ferramentas\agendar_empresas.ps1`. Cria a tarefa semanal "Alumia Aqui - empresas" (domingo, 20h; se o computador estiver desligado, roda quando ligar). A Receita publica uma vez por mês: nas outras semanas o script não baixa nada nem envia mudanças. Registro da última execução: ferramentas/ultima_execucao_empresas.log.
- **Instalar o site:** `npm install`, dentro de site/.
- **Ver o site:** `npm run build` e depois `npm run preview`, dentro de site/. A busca só funciona depois do build, porque o índice é gerado nele.

- **Publicar:** automático, pelo GitHub Actions (.github/workflows/publicar.yml). Roda a cada push na main, todo dia às 05:17 e sob demanda. Precisa do segredo ALUMIA_CHAVE no repositório, com o mesmo valor do .env local.

## 3 - Stack

- **Python:** coleta e tratamento dos dados.
- **GitHub Actions:** atualização periódica dos dados.
- **Astro:** geração das páginas estáticas.
- **Pagefind:** busca no navegador, sem servidor.
- **GitHub Pages:** hospedagem. O Cloudflare Pages gratuito limita o site a 20 mil arquivos, e o Alumia Aqui passa de 40 mil.

## 4 - Fontes de dados

Em uso: TSE (candidaturas, bens, fotos), Câmara e Senado (mandatos, proposições, cota, página do deputado), CGU (CEIS, CNEP, CEAF) e Receita Federal (sócios de empresas).

Próximas do TSE: certidões e contas de campanha.

Previstas: PNCP, Obrasgov e emendas parlamentares (Portal da Transparência).

TODO: documentar campos e forma de acesso de cada fonte em docs/fontes.md.

## 5 - Roadmap

0. Dados do TSE e página simples por candidato.
1. Site publicado com busca, disclaimer e página "Como funciona".
2. Mandatos: Câmara e Senado.
3. Sanções e empresas: TCU, CGU, CNJ, sociedades.
4. Aba educativa: poderes, cargos, processos públicos.
5. Contratos e obras: PNCP e Obrasgov.
6. Painéis (em andamento; candidaturas e Congresso publicados): visão geral dos candidatos e mandatos, com filtros (escolaridade, partido, cargo, UF, projetos aprovados, gastos de cota por partido, emendas parlamentares). Mesmas regras de neutralidade: sem ranking pronto, ordem padrão alfabética, valores comparáveis (por parlamentar, por mês) e fonte em cada número.
7. Praça: seção da comunidade para envio e avaliação de fontes.

## 6 - Licença

Código sob AGPL-3.0. Quem publicar versão modificada como site precisa publicar o código dessa versão.

Textos próprios do site (aba educativa, "Como funciona") sob CC BY 4.0. Dados oficiais pertencem às fontes de origem.
