# Changelog

## 0.1.0-alpha (not released yet)

First public test version, Windows first. See [the guide](docs/guide.en.md) for what you need and the known limits.

- **Workflow:** the project's actions (back, undo, test, project menu) in the top bar; the Campaign graph first, then one chapter's units, map and dialogues in the Chapters tab; explanations in help bubbles next to what they explain.
- **Characters:** starting level, average stats at a chosen level with promotions, affinities with the game's icons, portrait picked by its picture, gender following the class. A named ally's level is set on their sheet.
- **Battle colours:** a character's own colours by class, drawn from their portrait or painted on the sprite, with zoom, swapped by dragging, and your own colours kept when you try others.
- **Classes:** stats, animations with their empty movements marked, map sprites, generic portrait among the game's class cards and portraits.
- **Items:** magic weapons of any type (with a warning when a class has no ranged animation, and a "Strikes at range" filter in the animation library), icon picker, weapon effect, stat bonuses, rank points, properties (brave, unbreakable, no counter...), spell taken from another weapon, Use text; a new type brings what the engine expects of it.
- **Adding to the game:** characters, weapons, classes and chapters on the free slots of the game's tables; blank project starting from one empty chapter; choice of what a project keeps of the game.
- **Maps:** painting, terrain brushes that join by themselves, filling empty space, buildings as blocks, tile sheets and palette colours, resizing on all four sides, map changes on any map, villages, chests, doors and shops set in a list of map objects, Tiled import and export.
- **Chapters:** units (dropped item, computed stats, weapon ranks), units listed turn by turn with a turn shown on the map, automatic levels, enemy levels by difficulty, objectives with the game's icons, reach, staff range and danger zone; settings folded at the bottom of the sheet: convoy, preparations, fog, weather, battle background picked from a gallery, starting camera.
- **Scenes:** visual sequences, condition blocks, Yes / No questions and memories of the player's choices; scenes on a turn or a range of turns, on Talk, on an area or on a memory; commands for stats, HP, AI, side, leaving and rejoining the party, tile changes, weather, fog, screen tint, counters, sounds and warps; dialogues, quotes and supports.
- **Resources:** portraits, battle animations and map sprites from FE-Repo or your PC, with their authors in the project's credits.
- **Game options:** by category: HP bars and talk bubbles (working with every weather), beginner mode, quick experience and level up, acting after Talk, no story intro, a Staff & Dance line in the Configuration menu.
- **Testing and sharing:** test in mGBA (Docker Desktop started by FE Maker when it does not answer), export as a `.ups` patch; each project's `CREDITS.txt` says that FE Maker is largely developed with generative AI.
- **Projects** carry over between versions: converted when opened, after a copy in `backups/`; a project from a newer version is refused.
