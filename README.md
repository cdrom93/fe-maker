# FE Maker

**FE Maker** est un éditeur open source pour créer des jeux tactiques sur le moteur de *Fire Emblem: The Sacred Stones* (GBA), aussi simple à prendre en main qu'un « RPG Maker ». Il s'appuie sur la [décompilation FE8](https://github.com/FireEmblemUniverse/fireemblem8u).

*FE Maker is an open source editor to make tactics games on the Fire Emblem: The Sacred Stones (GBA) engine, designed to be as easy to use as an "RPG Maker". It is built on top of the [FE8 decompilation](https://github.com/FireEmblemUniverse/fireemblem8u).*

> 🚧 Projet en phase 0 (audit et fondations). Rien n'est encore utilisable.
> *Project in phase 0 (audit and foundations). Nothing is usable yet.*

## Avertissement / Disclaimer

FE Maker n'est **pas affilié** à Nintendo ni à Intelligent Systems, et n'est pas approuvé par eux. *Fire Emblem* est une marque de Nintendo.
Ce dépôt ne contient **aucune ROM ni aucune donnée** issue des jeux : chaque utilisateur doit fournir sa propre copie légale de la ROM (FE8 US).

*FE Maker is **not affiliated** with or endorsed by Nintendo or Intelligent Systems. Fire Emblem is a trademark of Nintendo.
This repository contains **no ROM and no game data**: each user must provide their own legally obtained ROM (FE8 US).*

## Cloner le dépôt / Cloning

```bash
git clone --recursive https://github.com/cdrom93/fe-maker.git
```

## Compiler la décomp / Building the decomp

Prérequis / Requirements: Python 3.10+, Docker.

```bash
python docker/build.py --rom path/to/your/fe8.gba
```

Résultat / Output: `build/fireemblem8.gba` (`fireemblem8.gba: OK` = identique à l'original / identical to the original).

## Documentation

- [Cahier des charges](CAHIER_DES_CHARGES.md) (en français)
- [Crédits / Credits](CREDITS.md)

## Licence / License

[GPL-3.0](LICENSE)
