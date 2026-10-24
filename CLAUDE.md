# FE Maker — notes for Claude

FE Maker is an easy (« RPG Maker »-like) editor for Fire Emblem: The Sacred Stones (FE8 US), built on the fireemblem8u decomp (`decomp/`, git submodule). The specification `CAHIER_DES_CHARGES.md` is the reference; work goes phase by phase (section 4).

## Keep the docs up to date

Every commit that changes what FE Maker can do updates the docs in the same commit:

- `CAHIER_DES_CHARGES.md`, section 4: progress of the current phase (what is done, the date, what is left, what is not tested in game yet).
- `README.md`: the status banner (FR and EN) when a feature area is added.
- `docs/audit-decomp.md`: anything learned about the decomp (data formats, limits, original-game bugs).
- `CREDITS.md`: any code, data or idea taken from another project (FEBuilderGBA, FE-Repo...).
- This file: any new rule, pitfall or architecture fact worth knowing in a later session.
- `CLAUDE.local.md` (personal, not committed, if present): the current status and next steps.

Docs are written in French (README in French and English); code and comments in English; UI in FR, EN, ES and IT (`ui/src/locales/*.json`, flags in `LangFlag.svelte`): every new UI string goes into all four files (`tests/server/test_locales.py` checks they have the same keys).

## Rules

- Never commit ROMs, `.gba` files or assets extracted from the game. The decomp stays an unmodified submodule; modified decomp files exist only in the build overlay (the decomp has no license, so modified decomp code is never redistributed).
- Do not add fixes tied to the original FE8 story unless the user asks: tell the user instead. The goal is to let users rebuild everything from scratch; the original story is only test material.
- Everything mentioned in the UI is clickable and opens its sheet (spec principle 8): use `Mention` and the navigator (`ui/src/lib/navigation.svelte.ts`).
- Class gender is shown after the class name: ♂ blue, ♀ pink (`GenderSign`).
- FEBuilderGBA (GPL-3.0) may be used freely as a reference or source; credit it in `CREDITS.md`.
- Don't write things from scratch when an existing resource saves time and tokens: before coding a feature (engine behavior, ASM hack, event command, map/tile tool, data format reader, editor logic...), look at what already exists and reuse or adapt it when it fits. First FEBuilderGBA as a whole (its patches in `config/patch2/FE8U/`, its source code, its data/config files), then any other resource: FE-Repo / FEU (Fire Emblem Universe) hacks and tools, Event Assembler and its libraries, the decomp itself, Python/JS libraries. Check the license allows reuse and credit it in `CREDITS.md`.
- An unmodified project must rebuild the original ROM byte for byte: only write what changed (`changed_files()`, cparse re-renders only edited entries).
- Patches are `.ups`. BUGFIX build option exists but is off by default (3 decomp BUGFIX blocks don't compile).

## Architecture

- `server/fe_maker/` (Python, FastAPI): `api.py` endpoints, `project.py` (project folder: `fe-maker.json` + `data/*.json`, migrations, build), `builder.py` (Docker build), `validation.py` (problems shown in the UI), `emulator.py` (mGBA launch and controls), `ups.py`.
- `server/fe_maker/ferepo.py`: FE-Repo browser (index `file_urls.json` and downloaded files cached in the user's config dir `ferepo/`; licence and authors read from file names; `Project.update_credits` writes them to the project's CREDITS.txt). Tests mock `_download`: never download from tests.
- `server/fe_maker/decomp/`: reading and writing the decomp. `gamedata.py` (characters, items, classes, combat, chapters; apply order classes → characters → items → combat → chapters), `cparse.py` (designated-initializer parser), `combat.py`, `units.py` (unit groups, REDA paths, chapter event groups), `objectives.py` (goal settings + victory events; DecompData.read_objective / apply_objective), `maps.py` (map rendering, tileset sheet, layout encoding, terrain names; map changes, movement costs; painted layouts and edited change sets in project `data/maps.json`, applied by `DecompData.apply_maps`), `mapobjects.py` (villages, houses, chests, doors, cracked walls, snags found by terrain; their used state learned from the original changes per tileset; new objects get a map change and a location event at build time, `DecompData.apply_maps` / `_apply_map_events`; object settings in `data/maps.json` "objects"), `tileedit.py` (mirrored and turned metatiles added to a tileset's free slots, new 8x8 tiles for quarter turns; project `data/maps.json` "tilesets" by tile config name; rewrites the TileConfig `.bin` and the 4-bit grayscale `ObjectType` PNG, written by hand since Pillow cannot), `quotes.py` (battle quotes and death quotes tables, new quotes added before the end of the lists), `dialogues.py` (messages as steps: face, clear, move, say, code; parse/render round-trips all 3404 game messages; chapter scenes and their triggers; project `data/dialogues.json` by message id, applied by `DecompData.apply_dialogues`; `layout` cuts lines too wide for the box at build time, mirrored in `ui/src/lib/textLayout.ts` for the preview), `fonts.py` (glyph widths and glyph sheet of the game's fonts; cp1252 characters, accented letters written as `[é]` codes defined in an overlay `textdefs.txt` by `TextFile.render` / `changed_files`), `events.py` (event scripts as commands for the visual editor `ScriptEditor.svelte`; edited scripts in `data/dialogues.json` "scripts", `DecompData._apply_scripts`; event files load with `_load_event_sources`, without the chapter settings), `supports.py` (support pairs and their C/B/A conversations; edited list in `data/dialogues.json` "supports", new pairs' conversations are quotes of kind "support"; `DecompData._apply_supports`), `portraits.py` (128 x 112 portrait sheets <-> the decomp's four portrait files, mouth/eye detection; imported sheets in the project's `assets/portraits/`, data `data/portraits.json`, `DecompData.apply_portraits`; portrait ids start at 1; an id past the game's table (`first_new_id`, 173) is a new portrait `portrait_New<id>_*`, added to `data_portrait.s`, `portrait_pointer.h`, the table and `textdefs.txt` as `[FID_New<id>]`), `assets.py` (portraits, item icons, map sprites; `face_preview` = big dialogue portrait), `tweaks.py` (test start modes).
- `changed_files()` values are text, or bytes for binary files (`.mar` map layouts); the overlay writer handles both.
- `ui/` (Svelte 5 runes + TypeScript, Vite): one editor component per tab (`MapEditor.svelte` paints on a canvas from the tileset sheet `/api/maps/{id}/tileset.png`), `EditableList` (undo + autosave), `RecordList` (list with icon/suffix snippets).
- `docker/`: build image (Ubuntu 24.04, agbcc pinned). The decomp is mounted read-only, the working copy lives in a Docker volume, the overlay is applied with `rsync -rlp --checksum`.
- Before every commit, run what CI runs: `server/.venv/Scripts/python -m ruff check server tests docker` (lines up to 130 characters), `pytest tests/server`, and `npm run check` in `ui/`. CI failed silently for a dozen commits on 23/10/2026 because ruff was not run locally.
- Testing beside the user's running app: start a second server with `FE_MAKER_HOME=<scratch home>` (own settings, a copy of the `rom/` folder, own projects), `FE_MAKER_UI_DIST=<scratch build>` (`npx vite build --outDir <dir>`) and `--port 8766`. The user's server, project and `ui/dist` stay untouched.
- Tests: `tests/server` (no ROM, fictional fixtures in `tests/server/fixtures/decomp`); `tests/local` (needs the ROM and Docker, never in public CI).
- `tools/mgba-drive.ps1` (Windows, dev only): drives mGBA with key presses and screenshots for in-game checks. Only when the user is not using the PC: if mGBA loses focus, the keys go to other windows.
- Feedback tickets: `server/fe_maker/tickets.py` (stored in the user's config dir, `tickets/tickets.json` + `images/`, never in the repo), `TicketPanel.svelte` (side column opened by the header button), `ui/src/lib/appContext.svelte.ts` (tab / record / detail attached to a ticket; `RecordList` and `ChapterEditor` fill it). List open tickets with `python -m fe_maker.tickets`.

## Pitfalls already met

- The decomp checkout must use LF line endings (`core.autocrlf=false`, `core.eol=lf`), or the Linux build breaks.
- Text compression packs 2 bytes per symbol: odd-length names need `[.]` padding (`name_message`).
- Unit definitions set each unit's class in every chapter: a character class change must retarget unit defs. The character sheet is the only source of a named character's class: chapter edits never write `classIndex` for `CHARACTER_` units (class 0 = the character's class when a unit switches to a named character); only generic units (raw ids 0x80...) get a class per chapter.
- Weapon ranks a class cannot animate crash the battle animation (validation `noBattleAnimation`).
- Weapon locks: generic CA/IA_LOCK 1,2,4,5,6,7 are allocated automatically from items' `reservedFor`; LOCK_3 means monster weapon.
- Map tileset PNGs are inverted grayscale (index = 15 − v/17); map palettes: 5 normal then 5 fog palettes.
- Several chapters share an internal id: key chapters by index.
- Map layouts are keyed by layout id (file stem): several chapters can share one, so painting it changes all of them (the UI says so). Map change sets are keyed by layout id too (one per layout).
- Map checks against units (`_validate_chapter_maps`) only report what the project changed: the original game has units outside their map and under roofs removed by map changes.
- Bash heredocs passed through the tool break on some quote/backslash mixes ("unexpected EOF"): write the patch script to the scratchpad and run it.
- Editors loaded asynchronously (chapters, maps) must read `nav.focus` once their list is loaded: `followFocus` alone misses a link that mounted the tab.
- An item reservation equal to the original one is never rewritten (the original Mani Katti is reserved for nobody; an edited empty reservation means unrestricted).
- PowerShell eats backticks in inline scripts: edit files with the Edit tool or Python, not PowerShell strings.
- Docker fails to start when CPU virtualization is off in the BIOS (happened several times on the user's PC).
- Opening scenes often load units on other maps (cutscenes): `chapter_unit_groups` marks groups loaded before the last `LOMA` as "cutscene"; editing them does not change the battle.
- Bash heredocs passed through the tool can mangle `\b` in Python sources: edit regex code with the Edit tool.
  The same goes for `\n` and `\x00` in a heredoc'd patch script (they became real newlines and NUL bytes): write such scripts with the Write tool.
- `assets.portrait_names` (and other readers) are `lru_cache`d: copy the list before adding to it (`list(...)`), or every later call sees the additions.
- Svelte `$derived` lists already hold a record right after `list.update` adds it: take its index before saving ("Add a change" opened nothing because of this).
- Text byte counts (padding to even runs) use `texts.text_size`: an accented letter is one byte in the game, not its UTF-8 length.
- Map objects: only objects that are new on the painted map get automatic changes and events; original objects keep their original behavior (some are decoration without event) unless the project sets them. A change only counts for an object if it puts it in its used state (`USED_TERRAIN`): a village painted inside a brigand-ruin rectangle would else ruin the wrong village.
