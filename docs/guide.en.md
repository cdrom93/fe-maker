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

The tabs:

| Tab | What for |
|---|---|
| Characters, Classes, Items, Combat | The game's sheets; add characters, weapons, classes |
| Chapters | Units, inventories, objective, reinforcements |
| Campaign | How chapters follow each other; add a chapter, end the game |
| Maps | Paint, import or export to Tiled |
| Dialogues | Conversations, supports, scenes and their events (a scene's ⚙ button) |
| Game options | Starting settings, comfort, test options |

**▶ Test** compiles and starts the game in mGBA. **Export patch** gives the `.ups` to share.

The header's **Ticket** button notes a problem; "Send to GitHub" opens a filled-in report, which you read before sending it.

## Known limits of the alpha

- Added chapters take free slots of the game: 21 in an ordinary project, 41 in a blank one.
- Added weapons are copies of a game weapon (49 slots). No new usable items or staves.
- Music: a demo only, one MIDI for a chapter's player phase.
- World map: it can only be turned off.
- Generated title pictures: still rather far from the game's style.
- The game must be recompiled to show a change; there is no live preview.

This project is not affiliated with Nintendo or Intelligent Systems. Never share a ROM: share the patch.
