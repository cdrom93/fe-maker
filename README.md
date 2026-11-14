# FE Maker

**FE Maker** est un éditeur open source pour créer des jeux tactiques sur le moteur de *Fire Emblem: The Sacred Stones* (GBA), aussi simple à prendre en main qu'un « RPG Maker ». Il s'appuie sur la [décompilation FE8](https://github.com/FireEmblemUniverse/fireemblem8u). Alpha en préparation.

*FE Maker is an open source editor to make tactics games on the Fire Emblem: The Sacred Stones (GBA) engine, designed to be as easy to use as an "RPG Maker". It is built on the [FE8 decompilation](https://github.com/FireEmblemUniverse/fireemblem8u). Alpha in preparation.*

## Télécharger / Download

### [Télécharger FE Maker pour Windows / Download FE Maker for Windows](https://github.com/cdrom93/fe-maker/releases/latest/download/fe-maker-setup.exe)

Ce lien donne toujours la dernière version. / *This link always gives the latest version.*

1. Lancez le fichier téléchargé, `fe-maker-setup.exe`. Si Windows affiche « Windows a protégé votre ordinateur » (l'installateur n'est pas signé) : « Informations complémentaires », puis « Exécuter quand même ».
2. Suivez l'installation (pas besoin d'être administrateur, rien d'autre à installer) : FE Maker s'ouvre dans votre navigateur.
3. Donnez votre ROM de Fire Emblem: The Sacred Stones (USA), puis cliquez sur les boutons « Télécharger » de l'accueil. FE Maker se met ensuite à jour tout seul.

*1. Run the downloaded file, `fe-maker-setup.exe`. If Windows shows "Windows protected your PC" (the installer is not signed): "More info", then "Run anyway". 2. Follow the installation (no administrator rights, nothing else to install): FE Maker opens in your browser. 3. Give your ROM of Fire Emblem: The Sacred Stones (USA), then click the home page's "Download" buttons. FE Maker then updates itself.*

Windows 10 ou 11. Guide : [français](docs/guide.md), [English](docs/guide.en.md). Toutes les versions / *All versions*: [Releases](https://github.com/cdrom93/fe-maker/releases).

## Ce qu'on peut faire / What you can do

| | Français | English |
|---|---|---|
| Campagne | Graphe des chapitres, routes, liste « À faire » | Chapter graph, routes, to-do list |
| Unités | Personnages, classes, objets, armes, triangle des armes, couleurs en combat tirées du portrait | Characters, classes, items, weapons, weapon triangle, battle colours drawn from the portrait |
| Cartes | Peinture, terrains qui se raccordent tout seuls, bâtiments, villages, coffres et portes, aller-retour avec Tiled | Painting, terrains that join by themselves, buildings, villages, chests and doors, round trip with Tiled |
| Chapitres | Placement, IA, renforts, objectifs, portée et zone de danger | Placement, AI, reinforcements, objectives, reach and danger zone |
| Dialogues | Conversations, évènements, souvenirs des choix du joueur, répliques, soutiens | Conversations, events, memories of the player's choices, quotes, supports |
| Ressources | Portraits, animations de combat et sprites de carte du FE-Repo ou du PC, crédits automatiques ; préférés communs à tous les projets ; personnages et classes exportés et importés d'un projet à l'autre | Portraits, battle animations and map sprites from FE-Repo or your PC, automatic credits; favourites shared by all projects; characters and classes exported and imported from a project to another |
| Compétences | Plus de 200 compétences : passives, à déclenchement (Luna, Sol, Astra...), ordre des coups, auras des unités proches, soins au début du tour, carte et commandes (Canto+, Bourrasque, Échange...), cible de l'IA ; sur les fiches personnage et classe ou apprises par niveau, montrées sur la fiche de l'unité, nom et icône au déclenchement en combat (portées du C-SkillSys et du Skill System) | Over 200 skills: passive, triggered (Luna, Sol, Astra...), order of the rounds, auras of nearby units, heals at the start of the turn, map and commands (Canto+, Galeforce, Swap...), the enemy AI's target; on character and class sheets or learned by level, shown on the unit's status screen, name and icon when triggered in battle (ported from C-SkillSys and the Skill System) |
| Musique | Musiques du jeu et MIDI importés, écoutés dans FE Maker avec les instruments du jeu ; musique de chaque phase d'un chapitre, ouverture, thème de victoire, musique des combats, thèmes de chef, musique des scènes et des écrans, 16 pistes, instruments General MIDI et batterie complète | Game songs and imported MIDI files, heard in FE Maker with the game's instruments; each phase's music for a chapter, opening, victory theme, battle music, boss themes, scene and screen music, 16 tracks, General MIDI instruments and full drum kit |
| Options | Règles (force et magie séparées, compétences...), réglages de départ, confort (barres de PV, mode débutant...), projet vierge | Rules (Strength and Magic split, skills...), starting settings, comfort (HP bars, beginner mode...), blank project |
| Tester | Dans mGBA, depuis le début ou un chapitre ; export en patch `.ups` | In mGBA, from the start or a chapter; `.ups` patch export |

Interface en français et en anglais. / *Interface in French and English.*

## Avertissement / Disclaimer

FE Maker n'est **pas affilié** à Nintendo ni à Intelligent Systems, et n'est pas approuvé par eux. *Fire Emblem* est une marque de Nintendo. Ce dépôt ne contient **aucune ROM ni aucune donnée** issue des jeux : chacun fournit sa propre copie légale de la ROM (FE8 US).

*FE Maker is **not affiliated** with or endorsed by Nintendo or Intelligent Systems. Fire Emblem is a trademark of Nintendo. This repository contains **no ROM and no game data**: everyone provides their own legally obtained ROM (FE8 US).*

## IA / AI

FE Maker est **développé en très grande partie avec une IA générative** (Claude) : le code, la documentation et les traductions. Son auteur décide de ce qu'il fait et le teste en jeu. Aucune image ni musique générée par IA n'est fournie avec FE Maker. Le `CREDITS.txt` de chaque projet le rappelle, car les jeux compilés contiennent du code écrit par FE Maker.

*FE Maker is **largely developed with generative AI** (Claude): code, documentation and translations. Its author decides what it does and tests it in game. No AI-generated art or music ships with FE Maker. Each project's `CREDITS.txt` says so too, as the games it builds contain code written by FE Maker.*

## Utiliser / Use

- [Guide de démarrage](docs/guide.md) / [Getting started](docs/guide.en.md) : installation, premiers pas, limites connues / *install, first steps, known limits*
- [Changelog](CHANGELOG.md)

## Développer / Develop

Prérequis / *Requirements*: Python 3.10+, Node.js 20+, mGBA ; Docker Desktop, sauf sous Windows avec la chaîne d'outils de FE Maker (`server/fe_maker/native/`, [sans Docker](docs/sans-docker.md)) / *Docker Desktop, except on Windows with FE Maker's toolchain*.

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
