# Ressources de la communauté FEU triées pour FE Maker

Tri du 12/11/2026 (pages lues ce jour-là). Pour chaque ressource : ce que c'est, sa licence, son intérêt pour FE Maker.
Rien n'est intégré : chaque intégration attend l'accord de l'utilisateur, puis se crédite dans `CREDITS.md`.
Rappel : sans licence, on ne reprend que l'idée ou le format (code réécrit), en citant l'auteur ; on peut aussi lui demander son accord.

## À intégrer ou adapter

- **C-SkillSys 3.3.x** (Mokha Lee, https://feuniverse.us/t/fe8-modern-c-skillsystem-3-3-1-rc/24614/502, code https://github.com/MokhaLeee/fe8u-cskillsys-kernel) — **MIT**.
  Déjà porté dans FE Maker (`skills.py`, commit épinglé). La 3.3.1-RC n'annonce que des corrections de bugs : comparer notre commit épinglé avec la 3.3.1 et reprendre les corrections qui touchent nos ~220 compétences. Le message 502 (installer sa propre version modifiée dans FEBuilder) ne nous concerne pas.
- **ASM / C de Vesly** (https://feuniverse.us/t/veslys-asm-c/12011/384, code https://github.com/Veslyquix/ASM) — **pas de licence** (pas de fichier LICENSE ; il demande d'être crédité) : idées et comportements seulement, code réécrit en C dans l'overlay, ou accord demandé à Vesly.
  À reprendre en priorité : **MapFloodFix** (message 384, 30/10/2026) corrige un plantage rare du jeu d'origine (remplissage de la carte de déplacement sur une grande carte avec une unité à fort coût de terrain) ; FE Maker laisse faire de grandes cartes, donc à vérifier dans la décomp puis à proposer comme correctif. Idées pour plus tard : Wait AI, Prevent Attacking, AoE (attaques de zone), Modular Summon, Repair Items, Item Special Effect, AutoLevelUnits (niveau des renforts), soutien après un combat.
- **Modular Minimug Box** (Zane, https://feuniverse.us/t/fe8-modular-minimug-box-2018-its-here/4235, code https://github.com/ZaneAvernathy/ModularMinimugBox) — **MIT**.
  La petite fenêtre d'unité sur la carte, faite de modules à cocher (PV, niveau, objet, compétences…). Base possible d'une option « fenêtre d'unité » dans FE Maker (modules = cases à cocher), réécrite en C dans l'overlay ou assemblée telle quelle ; rejoint le « mini-portrait » qui reste à faire (phase 2).
- **Circles' Spell Animation Creator** (circleseverywhere, 2016-2017, https://feuniverse.us/t/fe6-7-8-circles-spell-animation-creator-updated-to-v1-1/1946) — **pas de licence**, outil Windows (Python empaqueté), arrêté depuis 2017.
  Son format de script (commandes C, images O/B) est celui de beaucoup de sorts du FE-Repo : en écrire notre propre lecteur pour l'**import de sorts** (phase 5, « Reste : sorts »), comme `banim_import.py` le fait pour les animations de combat. Format seulement, auteur crédité.
- **gif_to_gbafe_anime_script** (7743, https://feuniverse.us/t/software-to-create-gbafe-battle-animation-templates-from-gif-animation/16976, code https://github.com/FEBuilderGBA/gif_to_gbafe_anime_script) — **pas de licence**.
  Découpe un GIF en images numérotées avec leurs durées. Idée à reprendre (quelques lignes avec Pillow) : accepter un **GIF** à l'import d'animation (ticket 172) et dans le futur créateur d'animations.

## À garder comme référence

- **Hacker directement la décomp** (https://feuniverse.us/t/inquiry-on-the-feasability-of-hacking-with-the-decomp-directly/37320, 08/2026) — discussion, pas de code.
  Confirme le choix de FE Maker et signale la **PR #744 de fireemblem8u (« shiftability »)** : données et fonctions qui grandissent en place au lieu de pointer vers de l'espace libre. À suivre de près : elle pourrait débloquer « agrandir les tables » (classes, objets) en attente. Contrepartie citée : elle casse les patchs FEBuilder à adresses fixes (pas notre cas). Vérifier si elle est fusionnée avant d'avancer le sous-module.
- **Ultimate Tutorial 2.0** (https://tutorial.feuniverse.us/) — licence non indiquée ; tutoriel FE8 (buildfile, textes, graphismes, TSA, son, cartes, évènements, hacks moteur).
  Référence de vocabulaire et de formats pour les tooltips et le guide ; décrit le flux EA / FEBuilder, pas la décomp.
- **Buildfiling on Linux** (CT075, 08/2026, https://feuniverse.us/t/buildfiling-on-linux/37461) — sans licence ; ColorzCore de CT075 en **GPL-3.0**.
  Utile le jour du portage Linux de FE Maker (« Windows d'abord, Linux ensuite ») : quels outils marchent sous Linux. FE Maker compile la décomp (agbcc, make), pas des buildfiles EA, donc peu de chose à reprendre.
- **Auto TSA Generator and Installers** (Citrus, 12/11/2026, https://feuniverse.us/t/auto-tsa-generator-and-installers/38195) — pas de licence, scripts Python + Tiled + .bat, téléchargement Dropbox.
  Génère les TSA de menus personnalisés (et de la Modular Minimug Box). Référence si FE Maker édite un jour l'aspect des menus ; pas d'outil externe dans FE Maker, donc idée seulement.
- **The Grand Library of FEU** (Arch, 2018, https://feuniverse.us/t/the-grand-library-of-feu-under-construction/4053) — index de liens, sans licence, plus mis à jour depuis 2018.
  Porte d'entrée vers des tutoriels et docs par thème ; le « Getting Started » (déjà au §7 du cahier) est plus récent.
- **fefw-recomp** (Goldoire, https://github.com/Goldoire/fefw-recomp) — **GPL-3.0** ; portage PC de Fire Emblem: Fortune's Weave (Switch 2) par recompilation statique (nxrecomp), jeu fourni par l'utilisateur.
  Pas un outil GBA. Référence de méthode pour la phase 7 (recompilation, « apportez votre propre copie », aucun fichier du jeu dans le dépôt) et pour l'idée long terme d'autres moteurs (Switch / Switch 2).
- **GBA Maker** (ArturDuleba, https://arturduleba.itch.io/gba-maker) — payant, propriétaire, code assisté par IA ; crée des jeux GBA neufs (script façon PICO-8, cartes, tracker de musique, émulateur intégré).
  Rien à reprendre ; référence d'ergonomie (tout dans un seul outil, test immédiat) et son **multijoueur par câble link testé dans l'éditeur** rejoint le mode 2 joueurs (#14).

## Sans intérêt

- **Nightmare Modules** (https://feuniverse.us/t/nightmare-modules/108/5) — modules d'édition hexadécimale (2014-2015), liens morts depuis 2018. FE Maker lit les données dans les sources de la décomp ; le message 5 est une simple question.
- **GBAFE Master Toolbox** (https://feuniverse.us/t/gbafe-master-toolbox/988) — liste d'outils de 2015 (Nightmare, FEditor, Sappy…), liens anciens ; tout ce qu'elle couvre est remplacé par FE Maker ou par FEBuilderGBA, déjà en référence.
- **Accessible FE12 hacking** (HeartHero, 2020, https://feuniverse.us/t/accessible-fe12-hacking/9459/23) — outils pour FE12 (DS), sans code publié ; le message 23 n'est qu'un encouragement. Hors cible (GBA, puis Fates).

# Listes « awesome » triées pour FE Maker

Tri du 12/11/2026 de https://github.com/sindresorhus/awesome (liste de listes) : sous-listes lues, seuls les outils et bibliothèques concrets qui servent le projet sont gardés, avec leur licence (vérifiée sur le dépôt sauf mention « non vérifiée »).
FE Maker a déjà : glisser-déposer natif (séquences, dialogues), contrôle des clés de traduction (`tests/server/test_locales.py`), Pillow, mGBA pour les playtests, import Tiled. Rien n'est ajouté sans l'accord de l'utilisateur.

## Liste du développement GBA (awesome-gbadev), la plus proche du projet

https://github.com/gbadev-org/awesome-gbadev (lue en entier). Elle vise surtout les jeux GBA neufs (moteurs, bibliothèques C/C++) ; rien sur le moteur son m4a / MP2K du jeu, la compression LZ77 ou les sauvegardes, en dehors de la documentation.

- **Playtests et débogage** : **mGBA** (MPL-2.0, déjà utilisé) : scripts Lua, débogueur en ligne de commande et GDB ; le câble link local marche, le câble en réseau n'est que prévu (#14). **SkyEmu** (MIT) : émulateur pilotable par un **serveur HTTP** (touches, mémoire, captures) avec débogueurs du processeur et de la mémoire ; une solution de rechange aux playtests actuels si mGBA bloque. No$gba (gratuit, Windows) et Mesen : débogueurs graphiques pour inspecter la VRAM à la main pendant le développement, pas pour l'appli.
- **Mode 2 joueurs (#14)** : **gba-link-connection** (MIT, afska) : protocole Multi-Play du câble link jusqu'à 4 joueurs, bien documenté. Référence du protocole ; le code (C++17, extensions GCC) ne compile pas tel quel avec agbcc, à réécrire en C dans l'overlay. Complète le code de l'arène en lien déjà relevé dans la décomp.
- **Éditeur voisin** : **klo-gba.js** (MIT) : éditeur web des niveaux de Klonoa sur GBA, bâti par rétro-ingénierie : le projet le plus proche de FE Maker (éditeur de jeu GBA existant dans le navigateur) ; sa méthode pour trouver les adresses des données (points d'arrêt dans no$gba) peut servir pour les 6,7 % de données encore binaires.
- **Documentation** : **GBATEK** (matériel complet : fonctions du BIOS dont la décompression LZ77, port série et câble link, mémoire de sauvegarde) et **Tonc** (tuiles 4bpp, palettes, modes d'affichage). The Audio Advance et le tutoriel « Sound on the GBA » (stuij) : Direct Sound et mixage, pour comprendre ce que fait le moteur son quand on ajoute des pistes (patchs « 16 tracks » à reproduire). Guide de Headspin (archivé) : compression.
- **Graphismes** : Usenti (sans licence, Windows, 2008) : éditeur de bitmaps à palette, référence pour vérifier nos exports de tuiles et palettes ; le sélecteur de couleurs BGR555 (orangegb.com) pour contrôler une couleur à la main.
- **Décomps** : pokeruby (pret, sans licence) : organisation d'une décomp GBA (Makefile, script de liens, contrôle SHA1, comparaison de l'assembleur), même famille que fireemblem8u.
- **Écartés** : moteurs et bibliothèques pour écrire un jeu neuf (Butano, agb, natu, gba-toolchain en zlib qui ne pilote pas agbcc), moteurs son MOD/XM (maxmod, Krawall, Apex Audio : pas le moteur m4a du jeu), tests de précision des émulateurs, jeux homebrew, NanoBoyAdvance (archivé, sans débogueur), dkarm_gba_docker (dépôt disparu).

## À retenir (autres listes)

- **Écoute de la musique dans le navigateur** (phase 5 : « musiques écoutables avant de les choisir », listes Web Audio et Music) : **Tone.js** (MIT, `Tone.Sampler` joue des échantillons transposés sur tout le clavier, donc les instruments du jeu) avec **@tonejs/midi** (MIT, lit le fichier MIDI) ; côté serveur **mido** (MIT) pour lire et écrire les MIDI à l'import. Écartés : MIDI.js (vieux), soundfont-player (MIT mais archivé en 2023).
- **Tests de l'interface** (alpha, étape 9, point 2 : Playwright) : **playwright-python** et **pytest-playwright** (Apache-2.0) : les tests d'interface restent en Python, dans la suite pytest, sans second outillage Node. Pour comparer des captures (interface ou écran du jeu en playtest) : **pixelmatch** (ISC, Node) ou plus simplement une différence d'images avec Pillow / numpy déjà présents ; BackstopJS et reg-suit sont plus lourds que le besoin. **Schemathesis** (MIT) : tests générés depuis le schéma OpenAPI de FastAPI, pour trouver les requêtes qui font planter l'API.
- **Recherche dans les listes et palette de commandes** (tickets #38 chercher une commande en tapant, #45 recherche dans les descriptions) : **Fuse.js** (Apache-2.0), recherche approchée tolérante aux fautes. La palette de commandes cmdk-sv (MIT) est archivée : la faire nous-mêmes avec Fuse.js.
- **Composants Svelte 5** (liste Svelte) : **svelte-sonner** (MIT, notifications « compilation finie », « échec ») et **svelte-splitpanes** (MIT, panneaux redimensionnables carte / propriétés). À prendre seulement si nos composants maison ne suffisent pas (règle : interface cohérente). Svelte Flow (MIT) seulement si le déroulé des évènements devient un graphe ; Melt UI (MIT) inutile, nos tooltips existent.
- **Graphismes GBA** (listes Pixel Art et gbadev) : **SuperFamiconv** (MIT) : conversion image → tuiles 4bpp et 16 sous-palettes en mode `gba`, avec déduplication des tuiles ; référence (ou oracle de test) pour l'import de jeux de tuiles et la réduction à 16 couleurs, que l'on garde en Python. **GBATEK** et **Tonc** (documentation) : formats des tuiles, palettes, compression LZ77, fonctions du BIOS.
- **Traductions par la communauté** (plus tard, `es` et `it` gelés) : **Weblate** (GPL-3.0, gratuit pour les projets libres, lit nos fichiers JSON) ; Tolgee (Apache-2.0 en partie) en second choix.

## À garder comme référence

- **Cartes** : **LDtk** (MIT, éditeur de niveaux, couches automatiques par règles : idée pour poser les bords de tuiles tout seul) ; **Tiled** (éditeur GPL-2.0, libtiled BSD-2-Clause : doc du format .tmx déjà importé) ; **Tilemap Studio** (LGPL-3.0, éditeur de tilemaps GBA pensé pour les décomps pret) ; **Tessarium** (fermé) : modifier une tuile la change partout où elle est posée, idée d'ergonomie.
- **Évènements et dialogues en graphe** : Rete.js, Litegraph.js, Drawflow (MIT) et Dialogger (MIT d'après la liste) si un jour le déroulé passe en nœuds ; aujourd'hui une liste ordonnée suffit.
- **Décomps et éditeurs voisins** : **pokeruby / pokeemerald** (pret) pour les conventions d'une décomp GBA ; **klo-gba.js** (éditeur web de niveaux de Klonoa sur données rétro-ingéniées) comme exemple d'éditeur web GBA.
- **Distribution** : **PyInstaller** (GPL-2.0 avec exception pour le chargeur : on peut distribuer l'appli construite sous une autre licence) si FE Maker devient un exécutable unique ; **watchfiles** (MIT) si FE Maker doit suivre les fichiers modifiés hors de l'appli.

## Sans intérêt pour FE Maker

Listes Electron, Windows, C/C++, JavaScript, Canvas, design systems, Storybook, CLI, GitHub Actions, Game Boy (gbdev : GB/GBC seulement), apprentissage du gamedev, typographie, icônes, polices (Nunito déjà là), sécurité : rien de concret qui manque au projet, ou outils payants (Aseprite, Pro Motion). Les extensions FastAPI (websockets, profileur, évènements) sont surdimensionnées pour un serveur local à un seul utilisateur ; les tâches de fond intégrées à FastAPI suffisent. La liste Claude Code n'a pas pu être lue (page vide à la lecture).
