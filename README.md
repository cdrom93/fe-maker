# FE Maker

**FE Maker** est un éditeur open source pour créer des jeux tactiques sur le moteur de *Fire Emblem: The Sacred Stones* (GBA), aussi simple à prendre en main qu'un « RPG Maker ». Il s'appuie sur la [décompilation FE8](https://github.com/FireEmblemUniverse/fireemblem8u). Alpha en préparation.

*FE Maker is an open source editor to make tactics games on the Fire Emblem: The Sacred Stones (GBA) engine, designed to be as easy to use as an "RPG Maker". It is built on the [FE8 decompilation](https://github.com/FireEmblemUniverse/fireemblem8u). Alpha in preparation.*

## Ce qu'on peut faire / What you can do

| | Français | English |
|---|---|---|
| Campagne | Graphe des chapitres, routes, liste « À faire » | Chapter graph, routes, to-do list |
| Unités | Personnages, classes, objets, armes, triangle des armes, couleurs en combat tirées du portrait | Characters, classes, items, weapons, weapon triangle, battle colours drawn from the portrait |
| Cartes | Peinture, terrains qui se raccordent tout seuls, bâtiments, villages, coffres et portes, aller-retour avec Tiled | Painting, terrains that join by themselves, buildings, villages, chests and doors, round trip with Tiled |
| Chapitres | Placement, IA, renforts, objectifs, portée et zone de danger | Placement, AI, reinforcements, objectives, reach and danger zone |
| Dialogues | Conversations, scènes visuelles, souvenirs des choix du joueur, répliques, soutiens | Conversations, visual scenes, memories of the player's choices, quotes, supports |
| Ressources | Portraits, animations de combat et sprites de carte du FE-Repo ou du PC, crédits automatiques | Portraits, battle animations and map sprites from FE-Repo or your PC, automatic credits |
| Options | Réglages de départ, confort (barres de PV, mode débutant...), projet vierge | Starting settings, comfort (HP bars, beginner mode...), blank project |
| Tester | Dans mGBA, depuis le début ou un chapitre ; export en patch `.ups` | In mGBA, from the start or a chapter; `.ups` patch export |

Interface en français et en anglais. / *Interface in French and English.*

## Avertissement / Disclaimer

FE Maker n'est **pas affilié** à Nintendo ni à Intelligent Systems, et n'est pas approuvé par eux. *Fire Emblem* est une marque de Nintendo. Ce dépôt ne contient **aucune ROM ni aucune donnée** issue des jeux : chacun fournit sa propre copie légale de la ROM (FE8 US).

*FE Maker is **not affiliated** with or endorsed by Nintendo or Intelligent Systems. Fire Emblem is a trademark of Nintendo. This repository contains **no ROM and no game data**: everyone provides their own legally obtained ROM (FE8 US).*

## Utiliser / Use

- [Guide de démarrage](docs/guide.md) / [Getting started](docs/guide.en.md) : installation, premiers pas, limites connues / *install, first steps, known limits*
- [Changelog](CHANGELOG.md)

## Développer / Develop

Prérequis / *Requirements*: Python 3.10+, Node.js 20+, Docker Desktop, mGBA.

```bash
git clone --recursive https://github.com/cdrom93/fe-maker.git
python -m venv server/.venv
server/.venv/Scripts/python -m pip install -e "server[dev]"   # Linux/macOS: server/.venv/bin/python
cd ui && npm ci && npm run build && cd ..
server/.venv/Scripts/python -m fe_maker
```

L'interface s'ouvre sur http://127.0.0.1:8765 et demande votre ROM au premier lancement. / *The interface opens on http://127.0.0.1:8765 and asks for your ROM on first launch.*

- Tests sans ROM / *Tests without ROM*: `python -m pytest tests/server`
- Tests avec ROM, en local / *ROM tests, local only*: `FE_MAKER_ROM=path/to/fe8.gba python -m pytest tests/local -s`
- Interface en mode dev / *UI dev mode*: `cd ui && npm run dev`, avec le serveur lancé / *with the server running*
- Compiler la décomp seule / *Build the decomp alone*: `python docker/build.py --rom path/to/fe8.gba [--overlay DIR] [--bugfix]`

Documentation (en français, sauf l'architecture) / *Documentation (in French, except the architecture)*: [architecture](docs/architecture.md), [cahier des charges](CAHIER_DES_CHARGES.md), [audit de la décomp](docs/audit-decomp.md), [pièges](docs/pieges.md), [journal](docs/journal.md), études du dossier [docs](docs/).

## Crédits et licence / Credits and license

[Crédits / Credits](CREDITS.md) · [GPL-3.0](LICENSE)
