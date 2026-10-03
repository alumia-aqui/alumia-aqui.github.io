# Alumia Aqui

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

## 2 - Stack

- **Python:** coleta e tratamento dos dados.
- **GitHub Actions:** atualização periódica dos dados.
- **Astro:** geração das páginas estáticas.
- **Pagefind:** busca no navegador, sem servidor.
- **Cloudflare Pages:** hospedagem.

## 3 - Fontes de dados

Fase atual: dados do TSE (candidaturas, bens, certidões, contas de campanha).

Previstas: APIs da Câmara e do Senado, CGU/Portal da Transparência, TCU, CNJ, CNPJ da Receita Federal, PNCP e Obrasgov.

TODO: documentar campos e forma de acesso de cada fonte em docs/fontes.md.

## 4 - Roadmap

0. Dados do TSE e página simples por candidato.
1. Site publicado com busca, disclaimer e página "Como funciona".
2. Mandatos: Câmara e Senado.
3. Sanções e empresas: TCU, CGU, CNJ, sociedades.
4. Aba educativa: poderes, cargos, processos públicos.
5. Contratos e obras: PNCP e Obrasgov.
6. Praça: seção da comunidade para envio e avaliação de fontes.

## 5 - Licença

Código sob AGPL-3.0. Quem publicar versão modificada como site precisa publicar o código dessa versão.

Textos próprios do site (aba educativa, "Como funciona") sob CC BY 4.0. Dados oficiais pertencem às fontes de origem.
