# ai-comics — AI comic generation studio

Generic pipeline for generating full comic issues with AI and packing them as
.cbz. Supports multiple comic projects; each one lives in `projects/<name>/`
with its own scripts, model sheets, style refs and rules.

Current projects: `megaman-nam` (Novas Aventuras de Megaman 17–20 — see
`projects/megaman-nam/PROJECT.md`).

## Layout

- `pipeline/split_scripts.py` — per-issue script → `projects/<p>/jobs/<issue>/page_NN.json`.
  Run with `-p <project>` (optional when only one project exists).
- `pipeline/assemble_cbz.py` — approved pages → `projects/<p>/out/*.cbz`.
- `pipeline/status.py` — progress report across projects.
- `pipeline/make_lettering_guide.py` — per-issue lettering guide (which text
  goes in which balloon) for projects with `"lettering": "manual"` — those
  generate pages with EMPTY white balloons (correct shape/tail, zero text);
  Diego letters them manually.
- `pipeline/common.py` — project discovery/config.
- `projects/<name>/` — one folder per comic:
  - `project.json` — formats (issues, script pattern, page regex, aspect, cbz naming)
  - `PROJECT.md` — everything specific to this comic (sources, style, QC rules, special pages)
  - `charmap.json` — character keyword → model sheet mapping
  - `scripts_src/` — the page-by-page prompt scripts (copied from the source of truth)
  - `refs/model-sheets/`, `refs/style/` — reference images to attach to generations
  - `jobs/`, `work/` (gen/approved/state.json), `out/`
  - `projects/` itself is gitignored (generated scripts, refs, renders, .cbz
    output) — nothing under it is version-controlled.
- `_template/` (repo root, NOT under `projects/` — kept out so it stays
  version-controlled) — copy this to `projects/<name>/` to start a new comic
  project.

## How generation works

Use the `/gerar-paginas` skill — it drives Higgsfield (CLI `higgsfield`,
official skills in `.agents/skills/`) page by page with a visual QC + reroll
loop. Claude Code is the orchestrator and QC reviewer; there is NO Claude API
usage.

Cost rules (apply to every project) — real credit costs, verified 2026-08-08:
- Plus plan = 1000 credits/month. `nano_banana_pro` = 2 credits/gen (default),
  `nano_banana_flash` = 1.5 (cheap reroll). NEVER `gpt_image_2` (7 credits)
  or video models. One issue ≈ 150 credits including rerolls.
- Max 3 generation attempts per page, then flag `needs_review` for Diego.
- Check `higgsfield account status` before each batch; warn under 100 credits.

Project-specific rules (language, continuity, special pages) live in each
project's PROJECT.md — always read it before generating.
