# FE Maker getting started guide (alpha)

FE Maker is an easy editor for making a rom hack of Fire Emblem: The Sacred Stones (FE8, US version). It works on the game's decomp, not on the ROM: your changes are recompiled code, and you share your hack as a `.ups` patch.

## What you need

- **Windows 10 or 11** (Linux and macOS will come later).
- **Python 3.10 or later**: https://www.python.org/downloads/ (tick "Add Python to PATH" when installing).
- **Docker Desktop**, started: it compiles the game. If it does not start, virtualization (Intel VT-x, AMD-V) is probably off in the BIOS.
- **mGBA**, for testing: https://mgba.io/downloads.html
- **Your own ROM** of Fire Emblem: The Sacred Stones (USA, Australia), legally obtained. FE Maker does not distribute it and checks its checksum.

## Install and start

1. Unzip `fe-maker-<version>.zip` wherever you like.
2. Run `lancer-fe-maker.bat`. The first launch installs what is needed, then opens the interface in your browser.
3. Give your ROM. The home page shows what is still missing: the "Download" button fetches the game's code (a few minutes, once).
4. The first build prepares the tools: it can take several minutes.

## Make a hack

- **New project**: the original game, to change.
- **Blank project**: a single empty chapter, with no enemies or dialogue, to write your own story. The game's weapons, items and classes stay; you can also remove the characters.

A project opens on **Campaign**, the graph of your chapters. A chapter's sheet gives the steps in order: draw the map, place the units and set the objective, write the dialogues, test.

| Tab | What for |
|---|---|
| Campaign | How chapters follow each other, add a chapter, end the game, the "To do" list |
| Chapters | One chapter in three views: units and objective, map, dialogues |
| Characters, Classes, Items, Combat | The game's sheets; add characters, weapons, classes |
| Game options | Starting settings, comfort, test options, what the project keeps |

A small **i** next to a title or an option holds its explanation: hover over it.

**▶ Test** compiles and starts the game in mGBA. The **Project** menu holds **Export patch**, which gives the `.ups` to share.

The **Ticket** button in the header notes a problem; "Send to GitHub" opens a filled-in report that you read before sending.

## Known limits of the alpha

- Added chapters take free slots of the game: 21 in an ordinary project, 41 in a blank one.
- Added weapons are copies of a game weapon (49 slots). No new usable items or staves.
- Music: a demo only, one MIDI for a chapter's player phase.
- World map: it can only be turned off.
- "End the game here" goes back to the title screen; the menu then offers to resume the last chapter.
- The copies in a project's `backups/` folder are restored by hand.
- The game must be recompiled to show a change; there is no live preview.

This project is not affiliated with Nintendo or Intelligent Systems. Never share a ROM: share the patch.
