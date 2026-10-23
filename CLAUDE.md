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

Docs are written in French (README in French and English); code and comments in English; UI in FR and EN (`ui/src/locales/*.json`).

## Rules

- Never commit ROMs, `.gba` files or assets extracted from the game. The decomp stays an unmodified submodule; modified decomp files exist only in the build overlay (the decomp has no license, so modified decomp code is never redistributed).
- Do not add fixes tied to the original FE8 story unless the user asks: tell the user instead. The goal is to let users rebuild everything from scratch; the original story is only test material.
- Everything mentioned in the UI is clickable and opens its sheet (spec principle 8): use `Mention` and the navigator (`ui/src/lib/navigation.svelte.ts`).
- Class gender is shown after the class name: ♂ blue, ♀ pink (`GenderSign`).
- FEBuilderGBA (GPL-3.0) may be used freely as a reference or source; credit it in `CREDITS.md`.
- An unmodified project must rebuild the original ROM byte for byte: only write what changed (`changed_files()`, cparse re-renders only edited entries).
- Patches are `.ups`. BUGFIX build option exists but is off by default (3 decomp BUGFIX blocks don't compile).

## Architecture

- `server/fe_maker/` (Python, FastAPI): `api.py` endpoints, `project.py` (project folder: `fe-maker.json` + `data/*.json`, migrations, build), `builder.py` (Docker build), `validation.py` (problems shown in the UI), `emulator.py` (mGBA launch and controls), `ups.py`.
- `server/fe_maker/decomp/`: reading and writing the decomp. `gamedata.py` (characters, items, classes, combat, chapters; apply order classes → characters → items → combat → chapters), `cparse.py` (designated-initializer parser), `combat.py`, `units.py` (unit groups, REDA paths, chapter event groups), `maps.py` (map rendering), `assets.py` (portraits, item icons, map sprites), `tweaks.py` (test start modes).
- `ui/` (Svelte 5 runes + TypeScript, Vite): one editor component per tab, `EditableList` (undo + autosave), `RecordList` (list with icon/suffix snippets).
- `docker/`: build image (Ubuntu 24.04, agbcc pinned). The decomp is mounted read-only, the working copy lives in a Docker volume, the overlay is applied with `rsync -rlp --checksum`.
- Tests: `tests/server` (no ROM, fictional fixtures in `tests/server/fixtures/decomp`); `tests/local` (needs the ROM and Docker, never in public CI).
- `tools/mgba-drive.ps1` (Windows, dev only): drives mGBA with key presses and screenshots for in-game checks.
- Feedback tickets: `server/fe_maker/tickets.py` (stored in the user's config dir, `tickets/tickets.json` + `images/`, never in the repo), `TicketDialog.svelte` (header button), `ui/src/lib/appContext.svelte.ts` (tab / record / detail attached to a ticket; `RecordList` and `ChapterEditor` fill it). List open tickets with `python -m fe_maker.tickets`.

## Pitfalls already met

- The decomp checkout must use LF line endings (`core.autocrlf=false`, `core.eol=lf`), or the Linux build breaks.
- Text compression packs 2 bytes per symbol: odd-length names need `[.]` padding (`name_message`).
- Unit definitions set each unit's class in every chapter: a character class change must retarget unit defs.
- Weapon ranks a class cannot animate crash the battle animation (validation `noBattleAnimation`).
- Weapon locks: generic CA/IA_LOCK 1,2,4,5,6,7 are allocated automatically from items' `reservedFor`; LOCK_3 means monster weapon.
- Map tileset PNGs are inverted grayscale (index = 15 − v/17); map palettes: 5 normal then 5 fog palettes.
- Several chapters share an internal id: key chapters by index.
- PowerShell eats backticks in inline scripts: edit files with the Edit tool or Python, not PowerShell strings.
- Docker fails to start when CPU virtualization is off in the BIOS (happened several times on the user's PC).
