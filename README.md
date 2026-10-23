# FE Maker

**FE Maker** est un éditeur open source pour créer des jeux tactiques sur le moteur de *Fire Emblem: The Sacred Stones* (GBA), aussi simple à prendre en main qu'un « RPG Maker ». Il s'appuie sur la [décompilation FE8](https://github.com/FireEmblemUniverse/fireemblem8u).

*FE Maker is an open source editor to make tactics games on the Fire Emblem: The Sacred Stones (GBA) engine, designed to be as easy to use as an "RPG Maker". It is built on top of the [FE8 decompilation](https://github.com/FireEmblemUniverse/fireemblem8u).*

> 🚧 En développement : personnages, objets (dont armes réservées), classes, triangle des armes et efficacités, unités des chapitres (placement sur la carte, ajout et suppression, personnage, classe, niveau, inventaire), bouton « Tester » et export en patch .ups. Avancement détaillé : [cahier des charges](CAHIER_DES_CHARGES.md), section 4.
> *In development: characters, items (including reserved weapons), classes, weapon triangle and effectiveness, chapter units (placement on the map, adding and deleting, character, class, level, items), "Test" button and .ups patch export. Detailed progress: [specification](CAHIER_DES_CHARGES.md), section 4.*

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

L'interface s'ouvre dans le navigateur (http://127.0.0.1:8765). Au premier lancement, elle demande votre ROM. Fermez la fenêtre de commande pour arrêter FE Maker ; si FE Maker tourne déjà, un nouveau lancement ouvre simplement le navigateur. Le bouton « Tester » demande que Docker Desktop soit démarré.
*The interface opens in your browser. On first launch it asks for your ROM. Close the command window to stop FE Maker; if FE Maker is already running, launching it again just opens the browser. The "Test" button needs Docker Desktop to be running.*

## Développement / Development

- Tests sans ROM / Tests without ROM: `python -m pytest tests/server` (après / after `pip install -e "server[dev]"`)
- Tests avec ROM, en local uniquement / ROM tests, local only: `FE_MAKER_ROM=path/to/fe8.gba python -m pytest tests/local -s`
- Interface en mode dev / UI dev mode: `cd ui && npm run dev` (le serveur Python doit tourner / the Python server must be running)
- Compiler la décomp seule / Build the decomp alone: `python docker/build.py --rom path/to/fe8.gba [--overlay DIR] [--bugfix]`

## Documentation

- [Cahier des charges](CAHIER_DES_CHARGES.md) (en français)
- [Audit de la décomp / Decomp audit](docs/audit-decomp.md) (en français) : ce qui est éditable, limites et bugs connus du jeu d'origine
- [Crédits / Credits](CREDITS.md)

## Licence / License

[GPL-3.0](LICENSE)
