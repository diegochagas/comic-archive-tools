---
name: gerar-paginas
description: Generate comic pages for an ai-comics project via Higgsfield, with visual QC and reroll loop. Use when the user asks to generate pages, continue generation, or QC pages (e.g. "/gerar-paginas megaman-nam 17", "gera as próximas páginas da edição 18", "continua a geração").
---

# Gerar Páginas — ai-comics

You are the orchestrator of a comic-page generation pipeline that supports
multiple comic projects (folders under `projects/`). The Claude API is NOT
used — you (the current Claude Code session) do the orchestration and visual
QC yourself, and Higgsfield does the image generation through its CLI, billed
in credits to Diego's Higgsfield Plus plan (1000 credits/month).

## Arguments

`/gerar-paginas [project] <issue> [pages]`
- `project`: folder name under `projects/` (e.g. `megaman-nam`). If omitted
  and only one project exists, use it; otherwise ask.
- `issue`: which issue to work on. `pages` optional ("5", "5-10", "5,7,9");
  without it, take the next pending pages in order.
- Process in batches of 5 pages, then report progress and continue.

## Before the first page of a session

1. Read `projects/<project>/PROJECT.md` — it holds the project-specific rules
   (QC priorities, special pages, language, continuity). Follow it.
2. Read `projects/<project>/project.json` for formats.
3. Check the credit balance: `higgsfield account status`. Warn Diego if the
   balance is under 100 credits; stop and ask if under 40.
4. Models & real credit costs (verified 2026-08-08 on the Plus plan, 1000
   credits/month):
   - **`nano_banana_pro` — 2 credits/gen — the default.** Best exact-text
     rendering + up to 14 image references, `aspect_ratio 2:3`,
     `resolution 2k`.
   - `nano_banana_flash` (Nano Banana 2) — 1.5 credits — fallback / cheap
     reroll when the failure was layout (not text).
   - Do NOT use `gpt_image_2` (7 credits) or any video model.
   - Full-issue budget check: 30 pages × ~2.5 attempts × 2 credits ≈ 150
     credits per issue. If the remaining balance can't cover the requested
     batch, tell Diego before generating.

## Per-page workflow

1. **Load the job**: `projects/<project>/jobs/<issue>/page_NN.json` — verbatim
   page prompt, issue preamble (base style), model sheets, exact dialogue
   strings, style refs, aspect.

2. **Build the generation request**:
   - Reference images: every file in `model_sheets` (from
     `projects/<project>/refs/model-sheets/`) + `style_refs` (from
     `projects/<project>/refs/style/`) + **the previously approved page of the
     same scene when the current page continues it** (keeps backgrounds and
     costumes continuous).
   - Characters in `no_sheet_characters` have no sheet: their look comes from
     the prompt text and from previously approved pages where they appeared —
     attach one of those as an extra reference.
   - Prompt: issue `preamble` + page `prompt` + a lettering suffix that
     depends on the job's `lettering` field:

     **`lettering: "manual"`** (Diego adds all text himself afterwards):
     "IMPORTANT — DO NOT RENDER ANY TEXT. Draw every speech balloon, thought
     balloon, scream balloon and caption box in the correct position, with
     the correct shape for its type (smooth oval for speech, cloud with
     bubble trail for thought, spiky burst for screams, rectangular box for
     captions/narration) and the tail pointing at the correct speaker — but
     leave the inside of every balloon and caption COMPLETELY EMPTY, pure
     flat white, no letters, no words, no gibberish, no pseudo-text. Size
     each balloon generously so the dialogue fits when added later. Also
     leave logo/title areas and any signs empty. Sound-effect onomatopoeia
     drawn as stylized art is allowed ONLY where the script explicitly asks
     for an SFX. Comic book page, portrait. Character appearance must match
     the attached model sheets."
     The dialogue in the script still matters: it tells you HOW MANY balloons
     each beat needs, of which type, attached to which character — reflect
     that in the prompt when useful (e.g. "Mega has two speech balloons in
     this panel").

     **`lettering: "ai"`**: "Render ALL dialogue and captions in <language>
     EXACTLY as written, letter by letter, inside the balloons/captions.
     Comic book page, portrait. Character appearance must match the attached
     model sheets."

3. **Generate** via the Higgsfield CLI (verified syntax, CLI v1.1.22):
   `higgsfield generate create <job_type> --prompt "<full prompt>"
    --image-references <ref1> --image-references <ref2> ...
    --wait --wait-timeout 10m`
   Local file paths are auto-uploaded. Download the result URL with curl to
   `projects/<project>/work/<issue>/gen/page_NN_try<K>.png`.
   If the prompt is too long for the shell, write it to a temp file and pass
   via command substitution.

4. **QC — look at the image** (Read the file) and check, in this order:

   For `lettering: "manual"`:
   a. **No text anywhere**: balloons, captions, logo areas and signs must be
      empty white — zero letters, zero gibberish/pseudo-text (the most common
      failure in this mode). SFX art only where the script asks for it.
   b. **Balloon inventory**: the number of balloons/captions roughly matches
      the lines in `dialogue_exact`, each with the right shape for its type
      (speech/thought/scream/caption) and the tail pointing at the correct
      speaker, big enough to hold its future text.
   c. **Story beats**: every beat in the prompt's STORY BEATS list is present.
   d. **Characters on-model**: faces, hair, outfit shapes and colors match the
      model sheets, plus any continuity rules from PROJECT.md.
   e. **Style**: consistent with the style refs and already-approved pages.

   For `lettering: "ai"`: same, but (a)+(b) are replaced by **dialogue
   accuracy** — every string in `dialogue_exact` appears EXACTLY, letter by
   letter, accents included.

5. **Decision**:
   - PASS → copy to `projects/<project>/work/<issue>/approved/page_NN.png`,
     set state `approved`.
   - FAIL → increment `tries`. If tries < 3: reroll with a **targeted fix**
     appended to the prompt. If the art is good and only balloon text is
     wrong, prefer an edit-style generation using the failed page as
     reference ("same image, fix only the balloon text to ...").
   - After 3 failed tries → state `needs_review` + note, move on. Never burn
     more than 3 generations on one page without asking Diego.

6. **Update `work/<issue>/state.json`** after every page (status, tries, notes).

## Field-tested lessons (from issue 17, pages 3-5)

- **Group images need itemized descriptions.** A model sheet showing a team
  (e.g. Os Cinco) is not enough — the model draws 2-3 of them. Describe each
  member in the prompt ("1. red/white with red crest; 2. bulky orange...").
- **Never put character names as list labels in a panel plan** — the model
  prints the labels onto the page as floating text. Describe panels in prose.
- **Whack-a-mole is real:** fixing one thing via full reroll often breaks
  another (a character vanishes, an outfit changes). After 2 full
  generations, switch to EDIT mode.
- **Edits: ONE change per call.** Nano Banana Pro edits (page as first
  reference + change instruction) preserve the rest of the page well — but
  only with a single change. Two changes in one edit caused a full relayout.
- **Anchor edits by content, not position** ("the panel with the 'Mentira!'
  balloon showing a brown-haired character"), and add explicit DO-NOT-CHANGE
  guards for elements a previous edit damaged (specific outfits, panels).
- **Check continuity against approved pages**: helmet on/off, eye colors,
  character count (e.g. exactly three aliens) — attach the relevant approved
  page as a reference when a scene continues.
- **Style-label leak ("NAM STYLE" printed on the page) recurs.** Always
  include an explicit "ABSOLUTE PROHIBITION: do not print the words
  '<style name>' or any style-label/watermark text" line in the prompt. If it
  leaks anyway, fix with a surgical edit (crop out the corner, don't reroll —
  rerolling risks changing character models).
- **Stage directions can leak into balloons as literal text.** A parenthetical
  like "(Kalinka, voice that doesn't tremble but should)" describes
  tone/acting for the artist, not dialogue — but the model sometimes prints
  it verbatim inside the balloon (in English). Watch for this specifically
  on lines with parenthetical acting notes; if it happens, call it out
  explicitly in the reroll prompt: "the balloon contains ONLY '<exact line>'
  — no stage direction, no English text."
- **A reroll that fixes one bug can silently break something else** (e.g.
  fixing balloon text caused Wily to lose his hair/mustache). Always
  re-check the WHOLE page after a fix, not just the part you targeted — a
  second small edit is often needed to restore what the reroll broke.
- **Edit-mode sometimes silently no-ops on subtle text-only fixes** (e.g. a
  duplicated phrase inside an otherwise-correct balloon) — the "edited"
  image comes back pixel-identical to the input. If an edit attempt doesn't
  visibly change anything after 1 retry, stop editing and do a **full
  reroll** instead, with an explicit warning about the specific error
  (e.g. "this line has two similar clauses — do not duplicate any words").
  Full rerolls have proven more reliable than edits for pure-text fixes.
- **Any edit can introduce a NEW typo elsewhere on the page while fixing the
  targeted issue** (e.g. an edit to remove a helmet corrupted "Holzenbein"
  into "Hoizenbein"/"Holzenhein" in two unrelated captions). After every
  edit, re-read ALL text on the page against the script — not just the part
  you changed — before approving.

## Special pages

Follow the project's PROJECT.md (covers, editorial/typography pages, extras).
- In `lettering: "manual"` mode, typography-heavy pages (editorials, text
  pages) are generated as their VISUAL FRAME only: paper background, column
  layout, empty text areas, framed illustration boxes — Diego fills the text.
- In `lettering: "ai"` mode: one generation attempt; if long text isn't fully
  legible/exact, build the page as HTML styled per the project, render at
  page resolution and screenshot via the browser tools.

## Lettering guide (manual mode)

When an issue finishes (or on request), run
`python3 pipeline/make_lettering_guide.py -p <project> <issue>` — it writes
`projects/<project>/out/lettering_<issue>.md` listing, page by page, every
line in order with its balloon type and speaker, for Diego to letter from.

## Progress & wrap-up

- After each batch of 5: run `python3 pipeline/status.py -p <project>` and
  report approved / pending / needs_review, plus anything flagged.
- When all pages of an issue are approved:
  `python3 pipeline/assemble_cbz.py -p <project> <issue>` and send Diego the
  .cbz path.
- If the Higgsfield CLI reports auth errors, stop and ask Diego to run
  `higgsfield auth login` — never work around auth.
