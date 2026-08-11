# Projeto: <nome do quadrinho>

> Copie esta pasta para `projects/<nome-do-projeto>/`, preencha este arquivo e
> o `project.json`, e adicione os assets abaixo. Depois rode
> `python3 pipeline/split_scripts.py -p <nome-do-projeto>`.

## O que este arquivo deve conter

Tudo que é específico DESTE quadrinho e que o skill `/gerar-paginas` precisa
saber na hora de gerar e revisar páginas:

1. **Fontes** — onde vivem os roteiros originais (fora do repo), como
   atualizá-los.
2. **Estilo** — descrição do estilo visual (também deve estar no preâmbulo de
   cada roteiro), formato das páginas.
3. **Regras de QC específicas** — modo de letreiramento (`"lettering"` no
   project.json: `"manual"` = balões vazios, textos adicionados à mão depois
   com o guia de `make_lettering_guide.py`; `"ai"` = IA renderiza os textos
   exatos), idioma dos balões, o que é critério nº 1, estado/continuidade
   dos personagens, páginas especiais (capa, editorial, extras).
4. **Referências** — o que está em `refs/model-sheets/` e `refs/style/` e
   quando anexar cada coisa.

## Assets necessários na pasta do projeto

- `scripts_src/<roteiros>.md` — um arquivo por edição, com páginas marcadas
  por `=== PAGE N — TÍTULO ===` (ou ajuste `page_header_regex` no
  project.json). Cada página: STYLE, CHARACTERS, STORY BEATS + falas entre
  aspas (as falas entre aspas viram o checklist de QC automaticamente).
- `refs/model-sheets/` — turnarounds dos personagens (um arquivo por
  personagem/variação).
- `refs/style/` — 2–4 imagens âncora do estilo (páginas reais, arte final).
- `charmap.json` — mapeia palavras-chave de personagem → model sheets
  (copie o formato do projeto megaman-nam).

## Dica

Os roteiros do megaman-nam (`projects/megaman-nam/scripts_src/`) são o modelo
de formato que funciona bem — uma página por bloco, beats obrigatórios,
falas exatas entre aspas, preâmbulo com o estilo base.
