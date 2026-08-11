# ai-comics — estúdio de quadrinhos por IA

Pipeline genérico para gerar edições completas de quadrinhos com IA e empacotar
como `.cbz`. Cada quadrinho é um projeto em `projects/<nome>/`; o primeiro é o
**megaman-nam** (*Novas Aventuras de Megaman* 17–20).

`projects/` está no `.gitignore` (roteiros, refs, renders e `.cbz` gerados —
conteúdo grande e não versionado); o template para novos projetos vive em
`_template/` na raiz do repo por isso mesmo.

## Arquitetura (e por que é a opção mais barata)

| Papel | Ferramenta | Custo |
|---|---|---|
| Orquestração + QC visual | **Claude Code** (skill `/gerar-paginas`) | já incluso na assinatura — **sem Claude API** |
| Geração de imagem | **Higgsfield CLI** — `nano_banana_pro` (2 créditos/geração) | plano Plus: 1000 créditos/mês ≈ 500 gerações |
| Parsing, CBZ, estado | Scripts Python locais | zero |

Orçamento real (medido via `higgsfield generate cost`): uma edição de 30
páginas com ~2,5 tentativas/página ≈ **150 créditos** — as 4 edições do
megaman-nam cabem em um mês de plano Plus com folga. O skill confere o saldo
(`higgsfield account status`) antes de cada lote.

## Setup (uma vez — já feito)

```bash
npm i -g @higgsfield/cli
higgsfield auth login          # login na conta Higgsfield (navegador)
npx skills add higgsfield-ai/skills
```

Requisito local: `python3` com `Pillow`.

## Uso

```bash
# 1. dividir os roteiros de um projeto em jobs por página (já feito p/ megaman-nam)
python3 pipeline/split_scripts.py -p megaman-nam

# 2. abrir o Claude Code nesta pasta e rodar:
#    /gerar-paginas megaman-nam 17        → gera+QC as próximas páginas pendentes
#    /gerar-paginas megaman-nam 17 5-10   → páginas específicas

# 3. progresso
python3 pipeline/status.py

# 4. guia de letreiramento (o texto de cada balão, página a página)
python3 pipeline/make_lettering_guide.py -p megaman-nam 17
#    → projects/megaman-nam/out/lettering_17.md

# 5. quando a edição fechar (depois do letreiramento manual, re-salve as
#    páginas letreiradas em work/17/approved/ antes de montar)
python3 pipeline/assemble_cbz.py -p megaman-nam 17   # → projects/megaman-nam/out/Megaman17.cbz
```

**Letreiramento:** os projetos com `"lettering": "manual"` no project.json
geram as páginas com balões vazios (forma e posição certas, sem nenhum
texto) — os textos são adicionados manualmente depois, seguindo o guia. Para
deixar a IA renderizar os textos, use `"lettering": "ai"`.

Páginas que falharem 3x ficam `needs_review` no `work/<ed>/state.json` do
projeto — revise o motivo, ajuste o roteiro se preciso e rode o skill de novo.

## Começar um quadrinho novo

1. Copie `_template/` (na raiz do repo, fora de `projects/`) para
   `projects/<nome-novo>/`.
2. Preencha `PROJECT.md` (fontes, estilo, regras de QC, páginas especiais) e
   `project.json` (edições, padrão dos roteiros, nomes do cbz).
3. Adicione `scripts_src/` (roteiros página a página), `refs/model-sheets/`,
   `refs/style/` e `charmap.json` (use o megaman-nam como referência de formato).
4. `python3 pipeline/split_scripts.py -p <nome-novo>` e depois
   `/gerar-paginas <nome-novo> <edição>` no Claude Code.

## Projetos

- **megaman-nam** — Novas Aventuras de Megaman 17–20. Detalhes:
  [projects/megaman-nam/PROJECT.md](projects/megaman-nam/PROJECT.md).
  Roteiros-fonte: `~/Nextcloud/Documents/Reading/Novas Aventuras de
  Megaman/Megaman17..20.md` (se editar, re-copiar p/ `scripts_src/` e rodar o
  splitter; o estado das páginas já geradas é preservado).
