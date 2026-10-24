# Credits

Every source used by FE Maker (code, data, documentation, resources, community research) is listed here, with author, link and license. See section 2 of `CAHIER_DES_CHARGES.md`.

| Source | Authors | Link | License | Used for |
|---|---|---|---|---|
| fireemblem8u (FE8 decompilation) | FireEmblemUniverse contributors | https://github.com/FireEmblemUniverse/fireemblem8u | No license file found (checked 2026-10-18) — used as an unmodified Git submodule only | Game engine and data source |
| agbcc | pret contributors | https://github.com/pret/agbcc | GPL-2.0 (GCC-based) — downloaded and built inside the Docker image, not redistributed in this repo | GBA C compiler |
| FEBuilderGBA | FEBuilderGBA contributors | https://github.com/FEBuilderGBA/FEBuilderGBA | GPL-3.0 | Functional reference; map rendering method (metatiles, tile entries, terrain bytes) adapted from `ImageUtilMap.cs` in `server/fe_maker/decomp/maps.py`; `.mar` map format (via the decomp's `mar_to_map.py`); descriptions of the enemy AI values (`config/data/ai1_FE8`, `ai2_FE8`, `ai3_ALL`) used for the labels of the AI panel; map editor tools (tile palette next to the map, right click to pick a tile) modelled on its map editor (`MapEditorForm.cs`); the 128 × 112 portrait sheet layout (face, mini portrait, eye and mouth frames) read from `ImagePortraitForm.cs` (`DrawPortraitSeet` / `BuildPortraitSeet`) for portrait import in `server/fe_maker/decomp/portraits.py` |
