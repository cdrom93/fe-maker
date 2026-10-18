# Audit de la décomp FE8 (fireemblem8u)

> Phase 0. Réalisé le 18/10/2026 sur le commit `f2e1f060` de [FireEmblemUniverse/fireemblem8u](https://github.com/FireEmblemUniverse/fireemblem8u) (12/10/2026).
> À consulter avant de modifier la façon dont FE Maker lit ou écrit une donnée de la décomp (voir cahier des charges, section 6).
> Les chemins ci-dessous sont relatifs au dossier `decomp/`.

## 1. Résumé

| | |
|---|---|
| Compilation | ✅ `fireemblem8.gba: OK` via l'image Docker (`python docker/build.py --rom …`) |
| Modification triviale | ✅ Eirika `baseHP` 0 → 20 : un seul octet change dans la ROM, 36 PV constatés en jeu |
| Code du moteur | Quasi entièrement en C : 358 fichiers `.c`. Il ne reste que ~900 lignes d'assembleur ARM (`asm/arm.s`, `asm/arm_call.s`) |
| Données encore binaires | 1 297 `.incbin "baserom.gba"` dans 34 fichiers de `data/`, soit **~1,1 Mo (6,7 % de la ROM)**. Concerne surtout des graphismes de menus et des effets de combat (voir section 4) |
| Besoin de la ROM | **Oui, toujours** : ces 1,1 Mo sont lus dans `baserom.gba` à chaque compilation. Cohérent avec le cahier des charges : l'utilisateur fournit sa ROM |

**Conclusion** : toutes les données des phases 1 à 4 (personnages, classes, objets, chapitres, cartes, événements, textes, portraits) sont **lisibles et modifiables** dans des formats texte (C, JSON, TXT) ou image (PNG). Rien de bloquant n'a été trouvé pour la phase 1.

## 2. Tableau par type de donnée

| Donnée | Emplacement | Format | Lisible / modifiable | Compilé par | Phase |
|---|---|---|---|---|---|
| **Personnages** (94) | `src/data_characters.c` (`gCharacterData[]`), struct `CharacterData` dans `include/bmunit.h` | C, initialiseurs désignés (`.baseHP = 0,`) | ✅ Très lisible | agbcc | 1 |
| **Objets** (206) | `src/data_items.c` (`gItemData[]`), struct `ItemData` dans `include/bmitem.h` | C, initialiseurs désignés | ✅ | agbcc | 1 |
| Effets / bonus d'objets | `src/data_itembonus.c`, `src/data_itemuse.c` ; efficacités via le pointeur `pEffectiveness` | C | ✅ | agbcc | 1–2 |
| **Classes** (127) | `src/data_classes.c` (`gClassData[]`), struct `ClassData` dans `include/bmunit.h` | C, initialiseurs désignés | ✅ | agbcc | 2 |
| Terrains (coûts de déplacement, bonus) | `src/data_terrains.c` (référencés par les classes : `pMovCostTable`, `pTerrainAvoidLookup`…) | C (tables) | ✅ | agbcc | 2 |
| Soutiens | `src/data_supports.c` | C | ✅ | agbcc | 4 |
| **Textes** (~3 400 messages) | `texts/texts.txt` + codes de contrôle dans `texts/textdefs.txt` | Texte brut (`## MSG_xxx` puis le message, codes `[X]`, `[NL]`, `[LoadFace]`…) | ✅ Très lisible | `tools/textencode` → `src/msg_data.c` (compression Huffman) | 1 (noms), 4 |
| **Chapitres** (79 entrées) | `src/data/chapter_settings.json` | **JSON** (carte, météo, brouillard, musiques, rangs…) | ✅ Déjà en JSON | `tools/jsonproc` + gabarit `.json.txt` → `chapter_settings.h` | 3 |
| Ordre des chapitres / carte du monde | `src/chapterdata.c`, `src/events_wm.c`, `src/worldmap_*.c` | C | ✅ mais logique mêlée au code | agbcc | 3 |
| **Cartes : disposition** (69) | `graphics/map/layout/*.mar` + `*.json` (largeur, hauteur) | `.mar` binaire simple (indices de tuiles) + JSON | ⚠️ Lisible par script (`scripts/mar_to_map.py`, basé sur FEBuilderGBA) | `mar_to_map.py` → `.bin` | 3 |
| Cartes : tilesets (10) | `graphics/map/ObjectType*.png` + palettes `MapPalette*.pal` | PNG + palette | ✅ | `gbagfx` (+ compression LZ) | 3 |
| Cartes : terrain de chaque tuile | `graphics/map/*TileConfiguration*.bin` | **Binaire** | ❌ À décoder (format documenté par la communauté et par FEBuilderGBA) | `.incbin` d'un fichier du dépôt | 3 |
| Cartes : changements (portes, villages), animations | `src/data/map/change/*.json`, `obj_anim/`, `pal_anim/` + `.bin`/`.png` | JSON + binaire | ⚠️ Partiel | `jsonproc` | 3 |
| **Placement des unités** | `src/events/*-eventudefs.h` et `src/events_udefs.c` : tableaux `UnitDefinition` + positions `REDA` | C | ✅ Lisible ; positions, IA, objets, niveau | agbcc | 3 |
| **Événements** | `src/events/chXX-eventinfo.h` (déclencheurs : tours, conversations, villages, zones), `chXX-eventscript.h` (scripts) | C, **macros proches d'Event Assembler** (`MUSC`, `LOAD1`, `MOVE`, `Text_BG`, `TURN`, `House`, `Seize`…) | ✅ Lisible, mais il faut un générateur / analyseur pour un éditeur visuel | agbcc (macros de `include/EAstdlib.h`) | 4 |
| Magasins, pièges | `src/events_shoplist.c`, `src/events_trapdata.c` | C | ✅ | agbcc | 3 |
| **Portraits** | `graphics/portrait/portrait_<Nom>_{tileset,mouth,chibi}.png` + `_palette.agbpal` ; table `src/portrait_data.c` | PNG + palette + table C | ✅ | `gbagfx` | 1 (aperçu), 5 |
| Sprites de carte | `graphics/unit_icon/{wait,move}/*.png` + `palette/` ; tables `src/unit_icon_*_data.c` | PNG | ✅ | `gbagfx` | 5 |
| Icônes d'objets | `graphics/item_icon/*.png` | PNG | ✅ | `gbagfx` | 1 (aperçu), 5 |
| Animations de combat | `graphics/banim/` (PNG, palettes, TSA) + scripts d'animation `.s` | PNG + `.s` + pipeline de compression maison (`scripts/arm_compressing_linker.py`) | ⚠️ Complexe (voir `docs/banim_asset_extraction.md`) | multiple | 5 |
| **Musique** | `sound/songs/midi/*.mid` (589) + `sound/voicegroups/`, échantillons `.aif` | MIDI + assembleur | ⚠️ MIDI lisible ; l'instrumentation (voicegroups) est technique | `tools/mid2agb`, `aif2pcm` | 5 |
| Interface, menus, effets divers | `data/data_*.s` | **Binaire brut** issu de `baserom.gba` | ❌ | `.incbin` | hors périmètre |

## 3. Comment la décomp compile

1. `./build_tools.sh` compile les outils maison (`gbagfx`, `textencode`, `jsonproc`, `mid2agb`, `scaninc`…).
2. `make` convertit les PNG, JSON, textes et MIDI, compile le C avec **agbcc** (compilateur d'époque, reconstitué par pret), assemble avec `arm-none-eabi-as`, puis lie le tout avec `ldscript.txt`.
3. `sha1sum -c checksum.sha1` compare le résultat avec la ROM d'origine. Le test échoue normalement dès qu'on modifie quelque chose.

Dans FE Maker :
- `docker/Dockerfile` contient la chaîne complète, avec agbcc figé sur le commit `da598c1d`.
- `docker/build.py` vérifie le SHA1 de la ROM et monte le sous-module **en lecture seule**. Il compile dans une copie de travail (volume Docker `fe-maker-work`) et applique les fichiers du projet par-dessus (option `--overlay`).
- Première compilation : environ 10 minutes. Recompilation après une modification de données : quelques secondes, car seul le fichier modifié est recompilé.

## 4. Zones encore binaires (baserom)

Les plus gros blocs, sur 1,1 Mo au total :

| Fichier | Taille | Contenu identifié |
|---|---|---|
| `data/data_9A31F8.s` | 265 Ko | Animations de carte (gain de stats, effets d'écran) |
| `data/data_A3E4D4.s` | 178 Ko | Menu de fin de partie (épilogues des personnages) |
| `data/banim-ekrdragonfx.s` | 165 Ko | Effets du dragon (boss final) |
| `data/data_A21658.s` | 53 Ko | Fond du menu de sauvegarde |
| `data/data-ekrdk.s` | 53 Ko | Effets du Roi démon |
| `data/banim-efxlvupfx.s` | 48 Ko | Effets de montée de niveau |
| `data/data_5AA96C.s`, `data_59E8E0.s`, `data_A2EEF0.s`, `data_B12A60.s`… | < 50 Ko chacun | Graphismes d'interface, arène en lien, défilé des classes |

**Impact** : aucun pour les phases 1 à 4. Ces zones resteront lues depuis la ROM de l'utilisateur. Si un jour on veut les rendre éditables, la décomp avance d'elle-même sur ce point : les rapports dans `reports/` suivent sa progression.

## 5. Points d'attention

1. **Fins de ligne sous Windows.** Git pour Windows convertit la décomp en CRLF par défaut, ce qui casse la compilation Linux. `docker/build.py` règle le sous-module en LF (`core.autocrlf=false`, `core.eol=lf`) avant de compiler.
2. **Copie de la décomp dans le conteneur.** Certains fichiers versionnés correspondent à des règles du `.gitignore` de la décomp (par ex. `src/rom_header.s`). Il ne faut donc pas filtrer la copie avec ce `.gitignore`.
3. **Noms et descriptions** des personnages, classes et objets ne sont pas dans leurs structures. Celles-ci pointent vers un identifiant de texte (`nameTextId = 0x212`). Renommer un personnage revient donc à modifier `texts/texts.txt`.
4. **Prix des objets** : la décomp stocke `costPerUse`. Le prix affiché en magasin vaut `costPerUse × maxUses`. L'éditeur doit montrer le prix total.
5. **Stats de base** : les stats d'un personnage s'**ajoutent** à celles de sa classe (Eirika : 0 + 16 de classe = 16 PV). L'aperçu doit afficher le total.
6. **Champs hérités de FE7** dans `chapter_settings.json` (`HectorStory`, `EliwoodStory`, `LynStory`…) : ce sont des noms de champs de la structure, à masquer dans l'interface.
7. **Événements** : leur format (macros C) est proche d'Event Assembler, que les moddeurs connaissent bien. Un éditeur visuel devra analyser **et** générer ces macros. C'est le plus gros chantier technique des phases 3 et 4.
8. **Terrain des tuiles** (`TileConfiguration*.bin`) : c'est le seul format binaire nécessaire en phase 3, il faudra écrire un convertisseur.
9. **La décomp évolue** (commits récents, fichiers renommés). On fige le sous-module sur un commit précis et on refait cet audit avant chaque mise à jour.

## 6. Cadre légal : constats

- Le dépôt de la décomp contient lui-même des assets extraits du jeu (2 322 PNG, 589 MIDI, 439 AIF…). Ils restent **dans le sous-module** et ne sont jamais copiés dans le dépôt FE Maker (règle 2.1 respectée).
- Toujours **aucun fichier LICENSE** dans la décomp au commit audité. Conséquence pratique : les fichiers de la décomp modifiés par FE Maker (comme `data_characters.c` généré) ne doivent exister **que localement**, dans `build/`. Ils ne sont jamais commités ni distribués. Seuls le patch `.ups`/`.bps` et le projet JSON de l'utilisateur sont partagés.
- Les données importées depuis la décomp pour créer un projet (stats d'origine, etc.) sont produites sur la machine de l'utilisateur. Les tests automatiques de FE Maker utilisent des **données fictives** (cahier des charges, section 5).

## 7. Recommandations pour la phase 1

1. **Écriture** : pour les personnages et objets, FE Maker **génère entièrement** `src/data_characters.c` et `src/data_items.c` à partir du JSON du projet, puis les dépose dans l'overlay. C'est plus fiable que de modifier le fichier d'origine ligne par ligne.
2. **Lecture initiale** (création d'un projet à partir du jeu d'origine), deux options à trancher :
   - (a) analyser les initialiseurs C de la décomp (format régulier, mais il faut résoudre les constantes comme `CLASS_EIRIKA_LORD` à partir des `include/constants/*.h`) ;
   - (b) lire les tables directement dans la ROM compilée, grâce aux adresses du fichier `.map` et aux structures connues. C'est plus robuste aux changements de mise en forme de la décomp, mais ça dépend de la compilation.
   - Recommandation : **(a)**, plus simple à tester sans ROM, complétée par un test local qui vérifie que « import puis génération » recompile une ROM identique (`fireemblem8.gba: OK`).
3. **Textes** : générer un `texts/texts.txt` complet, celui d'origine avec les messages modifiés remplacés, dans l'overlay.
4. **Test de non-régression** clé, local avec ROM : un projet importé sans modification doit compiler une ROM **identique octet pour octet** à l'original.

## Sources

- Décomp : FireEmblemUniverse contributors, https://github.com/FireEmblemUniverse/fireemblem8u (pas de licence constatée)
- agbcc : pret contributors, https://github.com/pret/agbcc (GPL-2.0)
- Format `.mar` des cartes : `scripts/mar_to_map.py` de la décomp, qui cite FEBuilderGBA (`MapEditorForm.cs`), https://github.com/FEBuilderGBA/FEBuilderGBA (GPL-3.0)
