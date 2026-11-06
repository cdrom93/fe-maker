# Compilation sans Docker sous Windows : étude de faisabilité

Demandée par l'utilisateur le 06/11/2026 (cahier, section 4, alpha, étape 9). But : que les testeurs n'aient plus à installer Docker Desktop (lourd, et en panne quand la virtualisation est coupée dans le BIOS). Docker reste en secours.

## Ce que fait la compilation aujourd'hui

L'image Docker (`docker/Dockerfile`, `docker/entrypoint.sh`) fournit, pour le `Makefile` de la décomp :

| Besoin | Dans l'image | Licence |
|---|---|---|
| `agbcc`, `old_agbcc` (compilateur C du jeu) + sa libc | pret/agbcc, commit `da598c1` | GPL-2 (gcc), libc newlib (BSD) |
| `arm-none-eabi-as`, `ld`, `objcopy`, `strip` | binutils Ubuntu | GPL-3 |
| préprocesseur C (`cc -E` aujourd'hui) | gcc Ubuntu | GPL-3 |
| `make`, `sh`, `sed`, `find`, `iconv`, `sha1sum` | Ubuntu | GPL |
| outils de conversion `gbagfx`, `bin2c`, `scaninc`, `aif2pcm`, `mid2agb` | sources dans la décomp (`tools/`), compilées à chaque fois | MIT (fichier LICENSE de chacun ; pret) |
| `textencode` | idem | MIT (camthesaxman, en tête du fichier) |
| `jsonproc` | idem | **aucune licence** (pret/pokeemerald, Marcus Huderle) ; inja et nlohmann/json qu'il embarque : MIT |
| `libpng` (pour `gbagfx`) | Ubuntu | libpng (permissive) |
| Python 3 + numpy + Pillow (scripts de la décomp) | Ubuntu | PSF, BSD, HPND |
| la ROM de l'utilisateur (`baserom.gba`) | montée à la compilation | les fichiers `data/*.s` en reprennent des morceaux (`.incbin`) |

La compilation demande donc la ROM : impossible de la vérifier dans la CI publique. Le test à l'octet près se fait en local.

## Ce qui pose question

- **Licences** : seul `jsonproc` n'a pas de licence. Il n'est jamais redistribué si on le compile chez l'utilisateur depuis la décomp téléchargée ; sinon, le remplacer par un petit script Python à nous (4 modèles inja simples : changements de carte, animations de tuiles et de palettes, réglages des chapitres) qui donne le même texte.
- **GPL** (agbcc, binutils, make) : redistribuer les binaires oblige à fournir les sources correspondantes. Le plus simple est de ne rien redistribuer : télécharger depuis la source officielle, ou publier les sources exactes à côté des binaires dans la même release.
- **Shell** : le `Makefile` appelle `sh`, `sed -i`, `find`, `iconv -f UTF-8 -t CP932`, des scripts Python lancés par leur `#!` (`./scripts/compressor.py`, `#!/bin/python3` pour deux d'entre eux), `uname`.
- **Préprocesseur** : `cc -E` (gcc Linux) aujourd'hui ; sous Windows, `arm-none-eabi-cpp` ou le `cpp` de MinGW. À vérifier : même sortie, donc même ROM.

## Pistes

1. **Tout compiler chez l'utilisateur** au premier lancement, comme la décomp est déjà téléchargée : w64devkit (gcc MinGW, make, busybox ; ~69 Mo, release GitHub officielle), binutils ARM officiels (archive Arm de ~290 Mo, dont on ne garderait que 4 outils), sources d'agbcc et de libpng/zlib. Rien n'est redistribué. Premier lancement plus long et plus lourd.
2. **Chaîne prête, construite dans GitHub Actions** (runner Windows) : agbcc, binutils ARM réduits, make, busybox, outils MIT de la décomp, `jsonproc` remplacé par du Python ; une archive de quelques dizaines de Mo, sources GPL jointes à la release. Premier lancement rapide.

## Essai en local (06/11/2026) : réussi

Décomp intacte (commit `f2e1f060`) compilée sous Windows 11 sans Docker ni WSL : **ROM identique à l'octet près** (SHA-1 `c25b145e…` de `checksum.sha1`).

Outils utilisés : w64devkit 2.11.0 (gcc 16 MinGW, make, busybox), binutils de la chaîne Arm GNU 14.3.rel1 (Windows), Python 3.11 avec numpy et Pillow, zlib 1.3.1 et libpng 1.6.47 compilés en statique.

| Étape | Résultat | Durée |
|---|---|---|
| agbcc, old_agbcc, libgcc, libc (pret/agbcc `da598c1`) | compilés tels quels, **en série** (`-j1`, comme `build.sh` : en parallèle, `genrtl.h` manque) ; `agbcc_arm` inutile pour FE8 | 4 min |
| outils de la décomp (`make -f make_tools.mk`) | tous compilés tels quels (`gbagfx` avec libpng via `pkg-config`) | < 1 min |
| ROM, première fois | 3 corrections (ci-dessous), rien de changé dans la décomp | ~25 min |
| ROM après un petit changement (un `.c`, les réglages des chapitres) | identique au jeu | 30 s |

Corrections nécessaires, toutes hors de la décomp :

1. **Ligne de commande trop longue** : la règle `objects.lst` fait `echo` de ~1 900 objets, au-delà des 32 Ko de Windows. Remplacée dans un makefile ajouté (`make -f Makefile -f win.mk`) par `$(file >$@,$(ALL_OBJECTS))`, écrit par make lui-même.
2. **`os.system` passe par `cmd.exe`** sous Windows : `arm_compressing_linker.py` et `compressor.py` y lancent `./scripts/...`, `tools/gbagfx/gbagfx`, `cp`, `mv`, et les échecs passent en silence (symboles manquants seulement au lien final). Un `sitecustomize.py` dans le Python de la compilation fait passer `os.system` par `sh -c`.
3. **Scripts lancés par leur `#!`** : la règle des animations de combat est redonnée dans `win.mk` avec `$(PYTHON)` devant chaque script, et un `python3.exe` est mis dans le `PATH`.

Le préprocesseur était `cc -E` (gcc MinGW), comme `cc -E` dans Docker : même ROM.

**Point faible** : la première compilation est lente (~25 min, dont ~15 pour les 1 475 animations de combat : plusieurs processus par fichier, coûteux sous Windows). Ensuite le cache de la copie de travail ne refait que ce qui change ; l'étape des animations ne revient que si leur liste change (animations importées).

## Ce qu'il faudrait livrer (piste 2)

| Élément | Taille | Origine |
|---|---|---|
| `arm-none-eabi-as`, `ld`, `objcopy`, `strip` | 13 Mo | archive officielle Arm (GPL-3) |
| préprocesseur : `cpp` + `cc1` de MinGW ou d'Arm | ~38 Mo | GPL-3 |
| `make`, `busybox` (sh, sed, find, iconv, cp, mv, sha1sum…) | 1 Mo | w64devkit (GPL) |
| agbcc + libc + libgcc | 9 Mo | compilés depuis pret/agbcc (GPL-2, newlib) |
| outils de la décomp | 4,5 Mo | compilés **chez l'utilisateur** ou en CI depuis leurs dépôts pret (MIT) ; `jsonproc` (sans licence) compilé chez l'utilisateur ou réécrit en Python |
| numpy | 37 Mo | à ajouter aux dépendances de FE Maker (Pillow y est déjà) |

Soit ~65 Mo décompressés (~25 Mo en zip) plus numpy. Les sources GPL exactes (agbcc au commit fixé, binutils et gcc d'Arm, w64devkit) sont jointes à la release qui porte les binaires.

## Conclusion

Faisable, sans toucher à la décomp, avec Docker gardé en secours. Travail estimé pour l'alpha :

1. un workflow GitHub Actions (runner Windows) qui construit l'archive de la chaîne d'outils, sources jointes ;
2. dans `builder.py`, un second moteur « natif » : copie de travail et overlay en Python (à la place de `rsync`), `win.mk` et `sitecustomize.py` fournis par FE Maker, mêmes étapes que `entrypoint.sh` ; Docker seulement si la chaîne native manque ou échoue ;
3. `checks.py` : télécharger la chaîne au premier lancement (comme la décomp), plus de Docker dans les prérequis ;
4. préparer la copie de travail une fois au premier lancement (les ~25 min de la première compilation, avec une barre de progression), ou accélérer l'étape des animations ;
5. tests : `tests/local` compile la décomp intacte par les deux moteurs et compare les ROM.
