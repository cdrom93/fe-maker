# Séparer la force et la magie (ticket 27) : étude

Étude du 24/10/2026. Rien n'est encore fait dans le moteur ; ce document dit ce qu'il faut changer et propose un ordre de travail.

## Dans le jeu d'origine

FE8 n'a qu'une statistique, « For/Mag » (`pow`), qui sert aux armes physiques comme à la magie. Les patchs connus :

- FEBuilderGBA : la séparation n'existe que dans le Skill System (`skill…/PATCH_StrMagSplit_Unit`, `PATCH_StrMagSplit_Class`) et quelques patchs qui en tiennent compte (`SYSTEM/Level does not decrease with Promotion_with_strmag_split`).
- C-SkillSys (MokhaLeee, `fe8u-cskillsys-kernel`, licence MIT) : la version moderne, en C, avec la séparation force/magie. Mais c'est un « CHAX » : du code compilé à part puis inséré avec Event Assembler dans une ROM FE8U d'origine, à des adresses fixes (FE-CLib). Il ne se branche pas sur la compilation de la décomp que fait FE Maker, où les adresses changent à chaque modification. On peut s'en servir comme référence (MIT : crédit obligatoire), pas tel quel.

FE Maker compile la décomp : la séparation se fait directement dans le code C du moteur, ce qui est plus simple et plus propre qu'un patch.

### Reprendre le C-SkillSys tel quel ? (regardé le 24/10/2026)

Le dépôt `FireEmblemUniverse/fe8u-cskillsys` (MIT, Mokha Lee) contient bien la séparation : `Kernel/Wizardry/Common/StrMagSplit` (code C et accroches), `Data/StrMag` (tables Mag par personnage `PersonMagicInfo.c` et par classe `JobMagicInfo.c`, objet « Mag Booster »). Il se compile sous Linux avec devkitARM, son Event Assembler (branche `mokha-fix`), FE-CLib-Mokha et des outils Python, puis s'écrit sur une ROM FE8U **propre**.

Il s'accroche au jeu comme ceci : `ORG $17e34` puis un saut vers sa propre fonction (`UnitLoadStatsFromChracter`), c'est-à-dire le début d'une fonction du jeu remplacé, à son adresse d'origine. Environ 70 fichiers de ce type, plus des écritures au milieu de fonctions.

Notre ROM n'est pas propre : FE Maker la recompile, et chaque donnée modifiée décale les adresses. Mais le code du moteur, lui, reste identique, seulement déplacé, et le fichier `.map` de notre compilation dit où se trouve chaque fonction. Une piste réaliste :

1. compiler la décomp non modifiée une fois (c'est la ROM d'origine) et garder son `.map` ;
2. pour chaque adresse du C-SkillSys, trouver la fonction du jeu qui la contient et son décalage, puis l'adresse de cette fonction dans notre compilation ;
3. compiler le C-SkillSys avec ces adresses (références FE-CLib refaites depuis notre `.map`) et l'écrire après notre ROM, dans l'espace libre.

**Prototype du 24/10/2026 (soir)**, retiré du dépôt le 29/10/2026 (toujours dans l'historique git) : `docker/cskillsys/` (image `fe-maker-cskillsys` : devkitARM, ColorzCore compilé pour Linux avec .NET 6, outils d'Event Assembler ; `port.py` traduit les adresses, testé par `tests/server/test_cskillsys_port.py`). Résultats :

- le C-SkillSys (commit `f61f6c2`, avec FE-CLib-Mokha `3503999`, de la même époque) se compile dans Docker sur la ROM d'origine et démarre ;
- sur une ROM de FE Maker (projet « test » de l'utilisateur), 69 811 adresses sont traduites par symbole (la référence de FE-CLib vient de l'ELF de la décomp : mêmes adresses que notre ROM d'origine, une centaine de noms différents seulement), il ne reste qu'un conflit (intro de débogage, non installée) et la ROM se compile (18 Mo) ;
- son espace libre est déplacé après 16 Mo : les zones libres de la ROM d'origine qu'il utilise (0xB2A604, 0xEFB2E0) sont reconnues automatiquement, et nos données y débordent déjà de 0x4AA0 octets. Sur la ROM d'origine, ce déplacement marche ;
- mais sur la ROM du projet, le jeu reste sur un écran noir au démarrage (pas encore compris), et surtout le C-SkillSys **refait tous les textes du jeu** depuis sa propre copie (`Contents/Texts`, nouvel arbre de Huffman écrit dans le code) et remplace plusieurs tables (objets, sorts…) : il effacerait les modifications de FE Maker.

Conclusion : la traduction d'adresses marche, mais intégrer le C-SkillSys veut dire réconcilier ses données avec celles de FE Maker, partie par partie (textes, tables, sauvegarde), et recommencer à chaque version du C-SkillSys. Arrêté là, à la demande de l'utilisateur, pour revenir aux chapitres. La séparation force/magie écrite directement dans le moteur (plan plus haut) reste la piste la plus sûre.

Risques : une fonction du jeu que FE Maker réécrit (convoi, par exemple) et que le C-SkillSys accroche aussi ; ses textes, qu'il installe lui-même, alors que FE Maker réécrit la table des textes ; ses tables de données (compétences, Mag) qu'il faudrait éditer dans FE Maker. On aurait aussi les compétences, pas seulement la magie. Il faut un prototype (une image Docker avec ses outils, la traduction d'adresses, une vérification en jeu par playtest) pour savoir si ça tient.

## Piste retenue pour plus tard (25/10/2026)

Aucun patch existant ne modifie le code de la décomp : celui de FEBuilder (assembleur), la refonte de Mokha (2022, C + Event Assembler sur la ROM d'origine, sans licence indiquée, combat pas fini : https://feuniverse.us/t/fe8-c-ea-str-mag-split-rework-fix-on-expand-levelup-screen-fit-to-chax/14856) et le C-SkillSys visent tous la ROM d'origine. `MokhaLeee/cSkillsLite-fireemblem8u` est une décomp modifiée (MIT) mais ne parle pas de la magie.

Plan : écrire la séparation directement dans les fonctions de la décomp (comme `seize.py` / `convoy.py`, dans le dossier de compilation), en reprenant le **code C** du module force/magie du C-SkillSys (MIT, crédit dans `CREDITS.md`), surtout les parties difficiles : sauvegarde agrandie et écran de montée de niveau. Pas de patch compilé, pas de traduction d'adresses.

## Avancement (06/11/2026)

Choix faits en écrivant le moteur (`server/fe_maker/decomp/strmag.py`, option du jeu `strMagSplit`) :

- La magie est dans l'octet 0x3A de l'unité, comme dans le Skill System : elle suit l'unité dans toutes les copies du jeu (unités de combat, recrutement, tri de l'équipe aux préparatifs). Une table par numéro d'unité aurait été perdue à ces copies. Les bonus temporaires du #164, qui occupaient cet octet, passent alors dans une table par numéro d'unité en IWRAM ; le tri de l'équipe aux préparatifs les garde (ils suivent les unités dans une pile pendant le tri).
- Données : une table par classe (base, croissance, maximum, gain de promotion) et par personnage (base, croissance) dans `bmunit.c`, écrites depuis les valeurs « mag » du projet. Sans valeur : une classe qui a un rang de bâton, d'anima, de lumière ou de ténèbres prend les chiffres de sa force, les autres partent de 0 (croissance 5 % pour les génériques) ; un personnage d'une classe magique prend sa force, les autres 0 (croissance : le quart de celle de la force).
- Combat : la magie compte quand l'arme a `IA_MAGIC` (tomes) ou `IA_MAGICDAMAGE` (épées magiques à distance, qui gardent leur moitié) ; la force sinon. Bâtons : soins, précision et portée avec la magie. IA : dégâts estimés des tomes avec la magie.
- Sauvegardes : les unités sauvegardées n'ont pas un bit libre ; la magie de chaque emplacement va dans la zone des cartes bonus de la mémoire de sauvegarde (voir `docs/audit-decomp.md`), avec l'heure de la sauvegarde pour la reconnaître. Une sauvegarde faite avant l'option (sans ces octets) estime la magie depuis les données : base du personnage et de sa classe, gain de promotion, croissance moyenne pour les niveaux gagnés.
- Écrans : fiche d'unité (ligne « Mag » sous « Str », avec le bonus de l'arme équipée), montées de niveau en combat et sur la carte (la case de la constitution, qui ne monte pas, passe à la magie ; ordre du #165 : PV, For, Mag, Tech à gauche, Vit, Chance, Déf, Rés à droite).
- Objets : un bonus de magie (`statBonuses.mag`) pour les armes équipées, les fortifiants et les objets à utiliser ; l'arène attaque avec la magie pour une arme magique.
- Vérifié en jeu (`tests/local`, `test_magic_split_from_strength`) : attaque au tome = puissance + magie + bonus du tome ; fiche d'unité ; montée de niveau en combat (+1 en magie) ; magie gardée après une sauvegarde de mi-chapitre ; bonus temporaires (`test_copies_heal_and_protect_their_own_amount`, avec et sans l'option).

- FE Maker : avec l'option, colonne « Mag » après « For » (renommée) dans les fiches personnage (base, croissance, moyenne), classe (base, maximum, croissance, gain de promotion), objet (bonus) et dans les stats d'une unité du chapitre ; sans valeur saisie, la valeur par défaut du moteur s'affiche.

- Par défaut : l'option est cochée dans tout nouveau projet créé depuis FE Maker (vierge ou non) ; un projet existant garde son choix, et `Project.create` seul reste le jeu d'origine (reconstruction à l'identique).

- Liste des unités : page 2 « Str Mag Skl Spd Lck Def Res » ; la page n'a pas la place pour 8 nombres, la magie prend la place de l'affinité (toujours sur la fiche d'unité), et son tri remplace celui par affinité.
- Bonus temporaires sur la magie : 7e compteur de la table (bits 24-27), baissé à chaque tour, lu par `GetUnitMagicFem` ; gardé à la sauvegarde de mi-chapitre (4e octet dans la zone des cartes bonus). La ligne combats/victoires/défaites de la fiche d'unité (après une première partie finie) descend d'une ligne sous Rés.

Reste : aperçu du combat dans FE Maker ; ligne combats/victoires/défaites pas vue en jeu (montée de niveau sur la carte vue par l'utilisateur).

## Ce qu'il faut changer dans la décomp

Environ 80 endroits lisent ou écrivent `pow` (hors tables de données), dans une vingtaine de fichiers :

| Partie | Fichiers | Travail |
|---|---|---|
| Valeur de l'unité | `include/bmunit.h` (`struct Unit`) | `mag` dans l'octet libre `_u3A` |
| Données de base | `struct CharacterData` (octets libres `_u23`, `_u24`), `struct ClassData` (pas d'octet libre sûr) | base et croissance du personnage dans `_u23` / `_u24` ; pour les classes (base, maximum, gain de promotion, croissance des génériques), une table à part indexée par classe, écrite par FE Maker (comme le fait le Skill System) |
| Création des unités, niveaux automatiques | `src/bmunit.c` (`UnitInitFromDefinition`, autolevel, plafonds `UNIT_POW_MAX`) | même calcul pour `mag` |
| Combat | `src/bmbattle.c` (attaque : `battleAttack += unit.pow`), `src/bmitem.c` | `mag` quand l'arme est magique (anima, lumière, ténèbres) ou une épée magique à distance ; `pow` sinon |
| Montée de niveau, promotion | `src/bmbattle.c` (`CheckBattleUnitLevelUp`, `ApplyUnitPromotion`…), `src/banim-ekrlvup.c`, `src/mapanim_lvupfx.c` | un gain de plus ; les deux écrans de montée de niveau (combat et carte) ont 8 lignes : il faut en dessiner une neuvième ou réorganiser |
| Fiche d'unité | `src/statscreen.c`, `src/unitlistscreen.c` | une ligne « Mag » (nouveau libellé, place à trouver sur la page 1) |
| Objets | `src/bmusemind.c`, `src/bmitemuse.c`, `src/prep_itemuse*.c` (Énergiring, Esprit des dieux…) | un bonus `mag` pour les fortifiants ; « Énergiring » ne donne plus que la force, un nouvel objet pour la magie |
| Sauvegardes | `include/bmsave.h` (`GameSavePackedUnit`, `SuspendSavePackedUnit`), `src/bmsave.c` | **le format est plein** (20 octets de champs de bits, aucun bit libre) : il faut agrandir l'unité sauvegardée, donc revoir la place des blocs de sauvegarde en SRAM. C'est le point le plus délicat |
| IA, arène, liaison, debug | `src/cp_*.c`, `src/bmarena.c`, `src/bmreliance.c`, `src/uidebug.c` | lire la bonne statistique |

## Côté FE Maker

- Option du projet « Séparer la force et la magie » (désactivée par défaut : un projet non modifié doit rebâtir la ROM d'origine).
- Fiches personnage et classe : colonnes Mag (base, croissance, maximum, promotion), remplies au départ avec les valeurs de For/Mag pour les classes magiques et 0 (ou une valeur proposée) pour les autres.
- Aperçu du combat et validation (`validation.py`) avec la bonne statistique.
- Tests : `tests/server` pour les données ; `tests/local` pour la compilation ; playtest sans fenêtre pour vérifier en jeu une attaque magique et une montée de niveau.

## Ordre proposé

1. Sauvegardes : trouver la place en SRAM et agrandir l'unité sauvegardée (sinon rien ne tient d'un chapitre à l'autre).
2. Unité, données, combat, niveaux : la statistique existe et compte.
3. Écrans : fiche d'unité, montée de niveau, liste des unités.
4. Objets et IA.
5. Interface FE Maker et tests.

Gros chantier (plusieurs jours de travail suivi, tests en jeu à chaque étape). À lancer comme un projet à part, après accord.
