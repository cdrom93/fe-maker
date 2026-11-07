# FE Maker getting started guide (alpha)

FE Maker is an easy editor for making a rom hack of Fire Emblem: The Sacred Stones (FE8, US version). It works on the game's decomp, not on the ROM: your changes are recompiled code, and you share your hack as a `.ups` patch.

## What you need

- **Windows 10 or 11** (Linux and macOS will come later).
- **Python 3.10 or later**: https://www.python.org/downloads/ (tick "Add Python to PATH" when installing).
- **mGBA**, for testing: https://mgba.io/downloads.html
- **Your own ROM** of Fire Emblem: The Sacred Stones (USA, Australia), legally obtained. FE Maker does not distribute it and checks its checksum.

## Install and start

1. Unzip `fe-maker-<version>.zip` wherever you like.
2. Run `lancer-fe-maker.bat`. The first launch installs what is needed, then opens the interface in your browser.
3. Give your ROM. The home page shows what is still missing: the "Download" buttons fetch the game's code and the build tools (a few minutes, once). Nothing else to install: no Docker needed.
4. FE Maker then starts the game's first build by itself, in the background (about ten minutes, once): you can work meanwhile. After that, a test builds in under two minutes.

## Update

1. Unzip the new version into another folder and start it. Once all is well, delete the old one.
2. Your projects stay where they are: in `FE Maker Projects`, in your user folder, outside the app's folder. Your settings are kept too.
3. A project made by an older version is converted when opened if needed, after a copy of `data/` into `backups/`. A project saved by a newer version does not open: install that version.
4. A game started on an old test may stop working once the hack has changed: test on a new game.

## Make a hack

- **New project**: the original game, to change.
- **Blank project**: a single empty chapter, with no enemies or dialogue, to write your own story. The game's weapons, items and classes stay; you can also remove the characters.

A project opens on **Campaign**, the graph of your chapters. A chapter's sheet gives the steps in order: draw the map, place the units and set the objective, write the dialogues, test.

| Tab | What for |
|---|---|
| Campaign | How chapters follow each other, add a chapter, end the game, the "To do" list |
| Chapters | One chapter in three views: units and objective, map, dialogues; its settings (weather, battle background, camera, fog...) are folded at the bottom |
| Characters, Classes, Items, Combat | The game's sheets; add characters, weapons, classes; a character's battle colours, drawn from their portrait or painted on the sprite |
| Game options | Rules (Strength and Magic split, skills...), starting settings, comfort, unit screens, test options, what the project keeps |

In a chapter, an **event** is a moment of the game: its trigger says when it happens ("Start of turn 3"), its **sequence** what happens in order, and its **dialogues** the text shown. An event can come on a turn or over several turns, on Talk, when a unit stops in an area, or from a memory. **Quotes** (in battle, on death) are not events.

A small **i** next to a title or an option holds its explanation: hover over it.

**▶ Test** compiles and starts the game in mGBA. The **Project** menu holds **Export patch**, which gives the `.ups` to share.

The **Ticket** button in the header notes a problem; "Send to GitHub" opens a filled-in report that you read before sending.

## Known limits of the alpha

- Added chapters take free slots of the game: 21 in an ordinary project, 41 in a blank one.
- Added weapons and items are copies of a game item (49 slots); a copied potion or staff keeps the effect of a game item, with its own amounts.
- A sword, lance or axe that strikes at range needs an animation with the "Ranged attack" movement: most of the game's axes have none. The library's "Strikes at range" filter finds some in FE-Repo.
- Music: a demo only, one MIDI for a chapter's player phase.
- World map: it can only be turned off.
- Skills: up to 3 per character or class sheet; their names and descriptions are in English in the game.
- Portrait colours: the result is approximate, touch it up if needed; an imported animation does not protect its mount.
- Terrain brushes: the joins are worked out from the game's tiles; roads are the weak point, and the ground around a stroke may change a little.
- "End the game here" goes back to the title screen; the menu then offers to resume the last chapter.
- The copies in a project's `backups/` folder are restored by hand.
- The game must be recompiled to show a change; there is no live preview.

## AI and publishing

FE Maker is largely developed with generative AI (code, texts, translations). Your project's `CREDITS.txt` says so: keep this note if you publish your hack. On FE Universe, AI-generated art and music are banned and any AI use in code or writing must be disclosed ([policy](https://feuniverse.us/t/ai-policy-updated-2026-10/38008)). FE-Repo resources are published by the community: checking that they follow this policy is up to you.

This project is not affiliated with Nintendo or Intelligent Systems. Never share a ROM: share the patch.
