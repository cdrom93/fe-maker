# FE Maker — notes for Claude

## Keep the docs up to date

Every commit that changes what FE Maker can do updates the docs in the same commit:

- `CAHIER_DES_CHARGES.md`, section 4: progress of the current phase (what is done, the date, what is left, what is not tested in game yet).
- `README.md`: the status banner (FR and EN) when a feature area is added.
- `docs/audit-decomp.md`: anything learned about the decomp (data formats, limits, original-game bugs).
- `CREDITS.md`: any code, data or idea taken from another project (FEBuilderGBA, FE-Repo...).

Docs are written in French (README in French and English); code and comments in English.

## Rules

- Never commit ROMs, `.gba` files or assets extracted from the game. The decomp stays an unmodified submodule; modified decomp files exist only in the build overlay.
- Do not add fixes tied to the original FE8 story unless the user asks: tell the user instead.
- Everything mentioned in the UI is clickable and opens its sheet.
