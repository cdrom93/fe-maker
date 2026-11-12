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
