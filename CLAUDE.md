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
- This file: a new rule or architecture fact (keep it short: it is loaded in every session).
- `CLAUDE.local.md` (personal, not committed): rewrite its "Où on en est" bullets (no journal there).

Docs are written in French (README in French and English); code and comments in English; UI in French and English
for now (`ui/src/locales/fr.json`, `en.json`): every new UI string goes into both (`tests/server/test_locales.py`).
Spanish and Italian (`es.json`, `it.json`) are set aside, frozen and not loaded, until a more complete version.

## Rules

- Never commit ROMs, `.gba` files or assets extracted from the game. The decomp stays an unmodified submodule; modified decomp files exist only in the build overlay (the decomp has no license, so modified decomp code is never redistributed).
- Do not add fixes tied to the original FE8 story unless the user asks: tell the user instead. The goal is to let users rebuild everything from scratch; the original story is only test material.
- Everything mentioned in the UI is clickable and opens its sheet (spec principle 8): use `Mention` and the navigator (`ui/src/lib/navigation.svelte.ts`).
- Class gender is shown after the class name: ♂ blue, ♀ pink (`GenderSign`).
- No decorative emojis (ticket 54): an emoji only where it is an icon standing for something (map tools and objects, objective types, event commands, expression codes, markers like ⚠ ⭐ ✎); never put before the text of a button, link, title or sentence.
- To illustrate, use the game's own visuals first (weapon type and item icons, portraits, map sprites, terrain tiles, read from the decomp by `assets.py`), before an emoji or a drawn icon.
- FEBuilderGBA (GPL-3.0) may be used freely as a reference or source; credit it in `CREDITS.md`.
- Don't write things from scratch when an existing resource saves time and tokens: before coding a feature (engine behavior, ASM hack, event command, map/tile tool, data format reader, editor logic...), look at what already exists and reuse or adapt it when it fits. First FEBuilderGBA as a whole (its patches in `config/patch2/FE8U/`, its source code, its data/config files), then any other resource: FE-Repo / FEU (Fire Emblem Universe) hacks and tools, Event Assembler and its libraries, the decomp itself, Python/JS libraries. Check the license allows reuse and credit it in `CREDITS.md`.
- Where to look: FEU's "Getting Started" index of tutorials and FEBuilder docs (https://feuniverse.us/t/getting-started/10320); laqieer's FEBuilderGBA fork (https://github.com/laqieer/FEBuilderGBA, GPL-3.0, archived 20/10/2026: cross-platform core, CLI, decomp support preview, headless mGBA playtests).
- An unmodified project must rebuild the original ROM byte for byte: only write what changed (`changed_files()`, cparse re-renders only edited entries).
- Patches are `.ups`. BUGFIX build option exists but is off by default (3 decomp BUGFIX blocks don't compile).

## Architecture

- `server/fe_maker/` (Python, FastAPI): `api.py` endpoints, `project.py` (project folder: `fe-maker.json` + `data/*.json`, migrations, build), `builder.py` (Docker build), `validation.py` (problems shown in the UI), `emulator.py` (mGBA launch and controls), `ups.py`.
- `server/fe_maker/ferepo.py`: FE-Repo browser (index `file_urls.json` and downloaded files cached in the user's config dir `ferepo/`; licence and authors read from file names; `Project.update_credits` writes them to the project's CREDITS.txt). Tests mock `_download`: never download from tests. Battle animations are folders in its index (GitHub "tree" URLs): their files come from GitHub's contents API (60 requests an hour without an account, listings cached in `ferepo/folders/`); their weapons, for the library's weapon filter, come from one git tree request per top folder (`animation_weapons`, cached a week in `ferepo/weapons/`). Downloads use certifi's certificates (Windows' store failed on api.github.com, 29/10/2026).
- `server/fe_maker/decomp/`: reading and writing the decomp, one module per subject:
  - `gamedata.py`: characters, items, classes, combat, chapters; apply order classes → characters → items → combat → chapters. New characters take a free entry of the full table (`free_character_numbers`: raw-numbered, loaded by no unit): id `CHARACTER_NEW_<hex>`, constant added to `characters.h` at build time, own name text; allies below 0x46 (`BWL_ARRAY_NUM`), enemies above; `POST /api/characters/new`. New weapons (`ITEM_NEW_<hex>`, after the game's last item up to 0xFE) copy a model weapon's fields, its `spellassoc-data.c` line and its item-specific `data_banimconf.c` entries (`_with_new_item_copies`); consumables and staves act by item number in the engine, so only weapons; `POST /api/items/new`.
  - `cparse.py`: designated-initializer parser.
  - `combat.py`: weapon triangle and effectiveness.
  - `units.py`: unit groups, REDA paths, chapter event groups.
  - `objectives.py`: goal settings + victory events; DecompData.read_objective / apply_objective.
  - `maps.py`: map rendering, tileset sheet, layout encoding, terrain names; map changes, movement costs, terrain effects (`terrain_effects`: avoid / def / res bonuses, foot and horse costs, shown in the map editor); painted layouts and edited change sets in project `data/maps.json`, applied by `DecompData.apply_maps`; another tile sheet of the game per layout in "bases" (`base_choices`, `with_base`, `layout_assets`, `convert_by_terrain`): pass the base to everything that reads a layout's assets, and tile edits work on `tileedit.layout_for(base)`.
  - `mapobjects.py`: villages, houses, chests, doors, cracked walls, snags found by terrain; their used state learned from the original changes per tileset; new objects get a map change and a location event at build time, `DecompData.apply_maps` / `_apply_map_events`; object settings in `data/maps.json` "objects".
  - `tileedit.py`: mirrored and turned metatiles added to a tileset's free slots, new 8x8 tiles for quarter turns; project `data/maps.json` "tilesets" by tile config name; rewrites the TileConfig `.bin` and the 4-bit grayscale `ObjectType` PNG, written by hand since Pillow cannot.
  - `quotes.py`: battle quotes and death quotes tables, new quotes added before the end of the lists.
  - `dialogues.py`: messages as steps: face, clear, move, say, code; parse/render round-trips all 3404 game messages; chapter scenes and their triggers; project `data/dialogues.json` by message id, applied by `DecompData.apply_dialogues`; `layout` cuts lines too wide for the box at build time, mirrored in `ui/src/lib/textLayout.ts` for the preview.
  - `fonts.py`: glyph widths and glyph sheet of the game's fonts; cp1252 characters, accented letters written as `[é]` codes defined in an overlay `textdefs.txt` by `TextFile.render` / `changed_files`.
  - `events.py`: event scripts as commands for the visual editor `ScriptEditor.svelte`; edited scripts in `data/dialogues.json` "scripts", `DecompData._apply_scripts`; event files load with `_load_event_sources`, without the chapter settings.
  - `supports.py`: support pairs and their C/B/A conversations; edited list in `data/dialogues.json` "supports", new pairs' conversations are quotes of kind "support"; `DecompData._apply_supports`.
  - `portraits.py`: 128 x 112 portrait sheets <-> the decomp's four portrait files, mouth/eye detection; imported sheets in the project's `assets/portraits/`, data `data/portraits.json`, `DecompData.apply_portraits`; portrait ids start at 1; an id past the game's table (`first_new_id`, 173) is a new portrait `portrait_New<id>_*`, added to `data_portrait.s`, `portrait_pointer.h`, the table and `textdefs.txt` as `[FID_New<id>]`.
  - `seize.py`: who can seize: `CanUnitSeize` rewritten only when characters' `canSeize` change.
  - `convoy.py`: who opens the convoy and the chapters without it; `SupplyUsability` / `HasConvoyAccess` rewritten only when the project changes them; characters' `convoyAccess`, chapters' "convoy".
  - `story.py`: how chapters follow each other: MNCH / MNC2 / MNC3 / MNC4 / MoveToChapter commands, `DecompData.chapter_links`; edits are edited scripts in `data/dialogues.json` "scripts", shown in the "Story flow" tab `ChapterFlow.svelte`.
  - `banim.py`: battle animations read from the decomp's text scripts and PNG sheets, drawn as strips of frames for the Classes tab player: `/api/classes/{id}/animations`, `/api/animations/{n}/{mode}.png|json`.
  - `banim_import.py`: FEditor / FEBuilder animation scripts (from FE-Repo or the user's PC: a weapon's folder or .zip, `/api/animations/import/local`) and 248 x 160 frames converted to the decomp's files: frames cut into GBA sprites, packed in 256 x 64 sheets, origin (0x94, 0x58); `export_feditor` does the reverse; imported animations kept in the project's `assets/animations/<key>/`, `data/animations.json`, added after the game's at build time by `DecompData.apply_animations`: table, pointers, sheet externs, compressing linker list, one new `AnimConf_FEM_<class>` array per changed class.
  - `pieces.py`: whole buildings of the original maps, found by terrain, offered as blocks: `/api/maps/{id}/pieces`.
  - `tiled.py`: .tmx export / import in the community's tmx2ea layout; files in the project's `tiled/` folder.
  - `assets.py`: portraits, item icons, map sprites; `face_preview` = big dialogue portrait.
  - `tweaks.py`: test start modes.
- `changed_files()` values are text, or bytes for binary files (`.mar` map layouts); the overlay writer handles both.
- UI theme (25/10/2026, from the clickable mockups https://claude.ai/artifact/MKewiQUGuDhGbfbYt1UGsL): colors, radii and the header colors are CSS variables in `ui/src/app.css` (`--header*`, `--radius-big`, light and dark); the font is Nunito, bundled with `@fontsource-variable/nunito` (no network). Use the variables, not new hard-coded colors; `button.play` is the green "Test" button. The screens' layouts follow the mockups one by one, when each screen is redone.
- `ui/` (Svelte 5 runes + TypeScript, Vite): one editor component per tab (the dialogue editor has a "conversation" view, `ConversationThread.svelte` + `FacePicker.svelte`, and the steps view) (`MapEditor.svelte` paints on a canvas from the tileset sheet `/api/maps/{id}/tileset.png`), `EditableList` (undo + autosave), `RecordList` (list with icon/suffix snippets).
- `docker/`: build image (Ubuntu 24.04, agbcc pinned). The decomp is mounted read-only, the working copy lives in a Docker volume, the overlay is applied with `rsync -rlp --checksum`.
- Before every commit, run what CI runs: `server/.venv/Scripts/python -m ruff check server tests docker` (lines up to 130 characters), `pytest tests/server`, and `npm run check` in `ui/`. CI failed silently for a dozen commits on 23/10/2026 because ruff was not run locally.
- Testing beside the user's running app: start a second server with `FE_MAKER_HOME=<scratch home>` (own settings, a copy of the `rom/` folder, own projects), `FE_MAKER_UI_DIST=<scratch build>` (`npx vite build --outDir <dir>`) and `--port 8766`. The user's server, project and `ui/dist` stay untouched.
- Tests: `tests/server` (no ROM, fictional fixtures in `tests/server/fixtures/decomp`); `tests/local` (needs the ROM and Docker, never in public CI).
- `server/fe_maker/playtest.py` + `docker/playtest/` (image `fe-maker-playtest`: mGBA 0.10.5 static lib + `driver.c`, a stdin/stdout line protocol): play a built ROM without any window, about 100 times faster than real time. `Game(rom, map_path)` holds keys for N frames, reads/writes memory by decomp symbol (`BuildOutput.map_path`, the build's `fireemblem8.map`), takes screenshots; `chapter()`, `turn()`, `phase()`, `units()`. Use it for in-game checks: it works while the user is on the PC. Example: `tests/local/test_playtest.py`.
- "Test this chapter": test option `chapter` (fe-maker.json testOptions), `tweaks.start_on_map(source, chapter)` sets `gPlaySt.chapterIndex` after `WriteNewGameSave` in the quick start, then loads the chapter's player units (`LoadUnits(GetChapterAllyUnitDataPointer())`, ticket 45: chapter 1 loads none, it moves the army of the chapters before; event loads reuse units already there).
- `server/fe_maker/__main__.py`: a launch while FE Maker runs restarts it (`POST /api/shutdown`, refused with 409 during a build; an older server without it is killed by the PID listening on the port, Windows only). My own server on 8765 is replaced too when the user clicks the shortcut.
- Feedback tickets: `server/fe_maker/tickets.py` (stored in the user's config dir, `tickets/tickets.json` + `images/`, never in the repo), `TicketPanel.svelte` (side column opened by the header button), `ui/src/lib/appContext.svelte.ts` (tab / record / detail attached to a ticket; `RecordList` and `ChapterEditor` fill it). List open tickets with `python -m fe_maker.tickets`.

## Pitfalls already met

In `docs/pieges.md`, by topic: Build et décomp, Données du jeu (personnages, classes, objets, textes), Cartes, Événements et enchaînement des chapitres, Tests en jeu (playtest), Outils et interface. Read the section of the area you work on before changing it, and add new pitfalls there.
