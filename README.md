# FE Maker

**FE Maker** est un éditeur open source pour créer des jeux tactiques sur le moteur de *Fire Emblem: The Sacred Stones* (GBA), aussi simple à prendre en main qu'un « RPG Maker ». Il s'appuie sur la [décompilation FE8](https://github.com/FireEmblemUniverse/fireemblem8u).

*FE Maker is an open source editor to make tactics games on the Fire Emblem: The Sacred Stones (GBA) engine, designed to be as easy to use as an "RPG Maker". It is built on top of the [FE8 decompilation](https://github.com/FireEmblemUniverse/fireemblem8u).*

## Ce qu'on peut faire / What you can do

En développement / *In development* — avancement détaillé : [cahier des charges](CAHIER_DES_CHARGES.md), section 4.

| | Français | English |
|---|---|---|
| Unités | Personnages, classes (animations de combat, import depuis le FE-Repo ou le PC), objets et armes réservées, triangle des armes, efficacités | Characters, classes (battle animations, FE-Repo or PC import), items and reserved weapons, weapon triangle, effectiveness |
| Cartes | Peinture de tuiles, pinceaux de terrain qui se raccordent tout seuls, terrains et leurs effets, taille, bâtiments entiers, changements de carte, villages / coffres / portes automatiques, tuiles tournées, palettes et jeux de tuiles, brouillard de guerre, aller-retour avec Tiled | Tile painting, terrain brushes that join by themselves, terrains and their effects, size, whole buildings, map changes, automatic villages / chests / doors, turned tiles, palettes and tile sheets, fog of war, round trip with Tiled |
| Chapitres | Unités (placement, IA, inventaire, renforts), objectifs, page Campagne (enchaînement des chapitres, option sans carte du monde, liste « À faire ») | Units (placement, AI, items, reinforcements), objectives, Campaign page (story flow, no world map option, to-do list) |
| Dialogues | Conversations (mise en page automatique, accents), scènes et éditeur d'événements visuel, répliques de combat, soutiens | Conversations (automatic layout, accented letters), scenes and visual event editor, battle quotes, supports |
| Ressources | Import et ajout de portraits, bibliothèque FE-Repo (portraits, animations de combat, sprites de carte), crédits automatiques | Portrait import and new portraits, FE-Repo library (portraits, battle animations, map sprites), automatic credits |
| Options du jeu | Réglages de départ, confort (barres de PV, mode débutant, animations rapides...), ce que garde le projet | Starting settings, comfort (HP bars, beginner mode, quick animations...), what the project keeps |
| Tester | Bouton « Tester » (depuis le début ou un chapitre choisi), export en patch .ups | "Test" button (from the start or a chosen chapter), .ups patch export |

Interface en français et en anglais (espagnol et italien plus tard). / *Interface in French and English (Spanish and Italian later).*

## Avertissement / Disclaimer

FE Maker n'est **pas affilié** à Nintendo ni à Intelligent Systems, et n'est pas approuvé par eux. *Fire Emblem* est une marque de Nintendo.
Ce dépôt ne contient **aucune ROM ni aucune donnée** issue des jeux : chaque utilisateur doit fournir sa propre copie légale de la ROM (FE8 US).

*FE Maker is **not affiliated** with or endorsed by Nintendo or Intelligent Systems. Fire Emblem is a trademark of Nintendo.
This repository contains **no ROM and no game data**: each user must provide their own legally obtained ROM (FE8 US).*

## Cloner le dépôt / Cloning

```bash
git clone --recursive https://github.com/cdrom93/fe-maker.git
```

## Installer et lancer / Install and run

Prérequis / Requirements: Python 3.10+, Node.js 20+, Docker Desktop (démarré / running), mGBA.

Une seule fois / Once:

```bash
python -m venv server/.venv
server/.venv/Scripts/python -m pip install -e server      # Linux/macOS : server/.venv/bin/python
cd ui && npm ci && npm run build && cd ..
```

Lancer / Run:

```bash
server/.venv/Scripts/python -m fe_maker                  # Linux/macOS : server/.venv/bin/python
```

L'interface s'ouvre dans le navigateur (http://127.0.0.1:8765). Au premier lancement, elle demande votre ROM. Fermez la fenêtre de commande pour arrêter FE Maker ; si FE Maker tourne déjà, un nouveau lancement le redémarre (pour prendre une nouvelle version), sauf pendant une compilation : il ouvre alors simplement le navigateur. Le bouton « Tester » demande que Docker Desktop soit démarré.
*The interface opens in your browser. On first launch it asks for your ROM. Close the command window to stop FE Maker; if FE Maker is already running, launching it again restarts it (to load a new version), except during a build: then it just opens the browser. The "Test" button needs Docker Desktop to be running.*

## Développement / Development

- Tests sans ROM / Tests without ROM: `python -m pytest tests/server` (après / after `pip install -e "server[dev]"`)
- Tests avec ROM, en local uniquement / ROM tests, local only: `FE_MAKER_ROM=path/to/fe8.gba python -m pytest tests/local -s`
- Tickets de test saisis dans l'appli (bouton « Ticket ») / Test tickets written in the app ("Ticket" button): `python -m fe_maker.tickets [--all]`
- Interface en mode dev / UI dev mode: `cd ui && npm run dev` (le serveur Python doit tourner / the Python server must be running)
- Compiler la décomp seule / Build the decomp alone: `python docker/build.py --rom path/to/fe8.gba [--overlay DIR] [--bugfix]`

## Documentation

- [Guide de démarrage](docs/guide.md) / [Getting started](docs/guide.en.md)
- [Changelog](CHANGELOG.md)
- [Cahier des charges](CAHIER_DES_CHARGES.md) (en français)
- [Audit de la décomp / Decomp audit](docs/audit-decomp.md) (en français) : ce qui est éditable, limites et bugs connus du jeu d'origine
- [Crédits / Credits](CREDITS.md)

## Licence / License

[GPL-3.0](LICENSE)
