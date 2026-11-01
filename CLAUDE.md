# FE Maker — notes for Claude

FE Maker is an easy (« RPG Maker »-like) editor for Fire Emblem: The Sacred Stones (FE8 US), built on the fireemblem8u decomp (`decomp/`, git submodule). The specification `CAHIER_DES_CHARGES.md` is the reference; work goes phase by phase (section 4).

## Keep the docs up to date (without rereading them)

Every commit that changes what FE Maker can do updates the docs in the same commit, touching only the lines concerned
(find them with grep, edit them with Edit; never reread a whole doc):

- `CAHIER_DES_CHARGES.md`, section 4: the "État" bullets of the phase concerned (done / left / not tested in game).
- `docs/journal.md`: one dated line appended at the end (the detailed history; never reread it whole).
- `README.md`: the table "Ce qu'on peut faire" only when a feature area is added.
- `docs/audit-decomp.md`: anything learned about the decomp (data formats, limits, original-game bugs).
- `docs/pieges.md`: a new pitfall, in its topic section.
- `CREDITS.md`: any code, data or idea taken from another project (FEBuilderGBA, FE-Repo...).
- `docs/architecture.md`: a new module or architecture fact, in English.
- This file: a new rule (keep it short: it is loaded in every session).
- `CLAUDE.local.md` (personal, not committed): rewrite its "Où on en est" bullets (no journal there).

Docs are written in French (README in French and English, this file and `docs/architecture.md` in English); code and comments in English; UI in French and English
for now (`ui/src/locales/fr.json`, `en.json`): every new UI string goes into both (`tests/server/test_locales.py`).
Spanish and Italian (`es.json`, `it.json`) are set aside, frozen and not loaded, until a more complete version.

### Doc cleanup routine

Regularly: after a big batch of work, before a release, or when the user asks. The one exception to "never reread a whole doc".

- `CAHIER_DES_CHARGES.md`, read whole: finished work summed up by phase, what is left and not tested in game checked against the code, open questions in section 8. Keep the section numbers (code, CI and `CREDITS.md` point to them) and every open item.
- `CLAUDE.md`: rules only, under 9 KB; module details go to `docs/architecture.md`.
- `README.md`, `CHANGELOG.md` (by theme), `docs/guide.md` and `docs/guide.en.md`: match what FE Maker does today.
- `docs/journal.md` and `docs/audit-decomp.md` are history and reference: leave them, apart from one journal line.
- Commit; push on the user's word.

## Rules

- Never commit ROMs, `.gba` files or assets extracted from the game. The decomp stays an unmodified submodule; modified decomp files exist only in the build overlay (the decomp has no license, so modified decomp code is never redistributed).
- Do not add fixes tied to the original FE8 story unless the user asks: tell the user instead. The goal is to let users rebuild everything from scratch; the original story is only test material.
- Every new game option goes in a category, never in a flat list: `SWITCH_GROUPS` in `gameoptions.py` (ticket 118); a new kind of option gets a new category with its `options.group.<name>` strings.
- Everything mentioned in the UI is clickable and opens its sheet (spec principle 8): use `Mention` and the navigator (`ui/src/lib/navigation.svelte.ts`).
- Class gender is shown after the class name: ♂ blue, ♀ pink (`GenderSign`).
- No decorative emojis (ticket 54): an emoji only where it is an icon standing for something (map tools and objects, objective types, event commands, expression codes, markers like ⚠ ⭐ ✎); never put before the text of a button, link, title or sentence.
- The UI stays neutral: no third-party hack or game named in its texts.
- Any action going back to the original game has the class `to-original` (hidden on request, ticket 137).
- No AI-generated art or music, no feature producing them from a prompt; FE Maker's AI use stays disclosed (spec, section 2, point 10).
- To illustrate, use the game's own visuals first (weapon type and item icons, portraits, map sprites, terrain tiles, read from the decomp by `assets.py`), before an emoji or a drawn icon.
- FEBuilderGBA (GPL-3.0) may be used freely as a reference or source; credit it in `CREDITS.md`.
- Don't write things from scratch when an existing resource saves time and tokens: before coding a feature (engine behavior, ASM hack, event command, map/tile tool, data format reader, editor logic...), look at what already exists and reuse or adapt it when it fits. First FEBuilderGBA as a whole (its patches in `config/patch2/FE8U/`, its source code, its data/config files), then any other resource: FE-Repo / FEU (Fire Emblem Universe) hacks and tools, Event Assembler and its libraries, the decomp itself, Python/JS libraries. Check the license allows reuse and credit it in `CREDITS.md`.
- Where to look: FEU's "Getting Started" index of tutorials and FEBuilder docs (https://feuniverse.us/t/getting-started/10320); laqieer's FEBuilderGBA fork (https://github.com/laqieer/FEBuilderGBA, GPL-3.0, archived 20/10/2026: cross-platform core, CLI, decomp support preview, headless mGBA playtests).
- An unmodified project must rebuild the original ROM byte for byte: only write what changed (`changed_files()`, cparse re-renders only edited entries).
- Patches are `.ups`. BUGFIX build option exists but is off by default (3 decomp BUGFIX blocks don't compile).

## Architecture

- Every module, data format and build step, one line each: `docs/architecture.md`. Read the lines of what you are about to change there; a new module or architecture fact goes there.
- `server/fe_maker/decomp/`: reading and writing the decomp, one module per subject; `gamedata.py` holds `DecompData`.
- `server/fe_maker/` (Python, FastAPI): `api.py` endpoints, `project.py` (project folder: `fe-maker.json` + `data/*.json`, migrations, build), `builder.py` (Docker build), `validation.py` (problems shown in the UI), `emulator.py` (mGBA launch and controls), `ups.py`.
- `changed_files()` values are text, or bytes for binary files (`.mar` map layouts); the overlay writer handles both.
- Workflow (30/10/2026): a project opens on Campaign; top tabs follow the work (`Workspace.TABS`), the Chapters tab has three views (`CHAPTER_VIEWS`: chapters, maps, dialogues) on one `currentChapter`. Explanations go in tooltips (`Help.svelte`, a small "i"), not in paragraphs; keep visible text short. UI words: a scene has a trigger, a sequence (« déroulé », never "script") and dialogues (never "conversation").
- UI theme (25/10/2026, from the clickable mockups https://claude.ai/artifact/MKewiQUGuDhGbfbYt1UGsL): colors, radii and the header colors are CSS variables in `ui/src/app.css` (`--header*`, `--radius-big`, light and dark); the font is Nunito, bundled with `@fontsource-variable/nunito` (no network). Use the variables, not new hard-coded colors; `button.play` is the green "Test" button. The screens' layouts follow the mockups one by one, when each screen is redone.
- `ui/` (Svelte 5 runes + TypeScript, Vite): one editor component per tab (the dialogue editor has a "conversation" view, `ConversationThread.svelte` + `FacePicker.svelte`, and the steps view) (`MapEditor.svelte` paints on a canvas from the tileset sheet `/api/maps/{id}/tileset.png`), `EditableList` (undo + autosave), `RecordList` (list with icon/suffix snippets).
- Before every commit, run what CI runs: `server/.venv/Scripts/python -m ruff check server tests docker` (lines up to 130 characters), `pytest tests/server`, and `npm run check` in `ui/`. CI failed silently for a dozen commits on 23/10/2026 because ruff was not run locally.
- Testing beside the user's running app: start a second server with `FE_MAKER_HOME=<scratch home>` (own settings, a copy of the `rom/` folder; projects still go to the real `FE Maker Projects` unless a path is given), `FE_MAKER_UI_DIST=<scratch build>` (`npx vite build --outDir <dir>`) and `--port 8766`. The user's server, project and `ui/dist` stay untouched.
- Tests: `tests/server` (no ROM, fictional fixtures in `tests/server/fixtures/decomp`); `tests/local` (needs the ROM and Docker, never in public CI).
- `server/fe_maker/playtest.py` + `docker/playtest/` (image `fe-maker-playtest`: mGBA 0.10.5 static lib + `driver.c`, a stdin/stdout line protocol): play a built ROM without any window, about 100 times faster than real time. `Game(rom, map_path)` holds keys for N frames, reads/writes memory by decomp symbol (`BuildOutput.map_path`, the build's `fireemblem8.map`), takes screenshots; `chapter()`, `turn()`, `phase()`, `units()`. Use it for in-game checks: it works while the user is on the PC. Example: `tests/local/test_playtest.py`.

## Pitfalls already met

In `docs/pieges.md`, by topic: Build et décomp, Données du jeu (personnages, classes, objets, textes), Cartes, Événements et enchaînement des chapitres, Tests en jeu (playtest), Outils et interface. Read the section of the area you work on before changing it, and add new pitfalls there.
