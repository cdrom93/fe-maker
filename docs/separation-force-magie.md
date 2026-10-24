# Séparer la force et la magie (ticket 27) : étude

Étude du 24/10/2026. Rien n'est encore fait dans le moteur ; ce document dit ce qu'il faut changer et propose un ordre de travail.

## Dans le jeu d'origine

FE8 n'a qu'une statistique, « For/Mag » (`pow`), qui sert aux armes physiques comme à la magie. Les patchs connus :

- FEBuilderGBA : la séparation n'existe que dans le Skill System (`skill…/PATCH_StrMagSplit_Unit`, `PATCH_StrMagSplit_Class`) et quelques patchs qui en tiennent compte (`SYSTEM/Level does not decrease with Promotion_with_strmag_split`).
- C-SkillSys (MokhaLeee, `fe8u-cskillsys-kernel`, licence MIT) : la version moderne, en C, avec la séparation force/magie. Mais c'est un « CHAX » : du code compilé à part puis inséré avec Event Assembler dans une ROM FE8U d'origine, à des adresses fixes (FE-CLib). Il ne se branche pas sur la compilation de la décomp que fait FE Maker, où les adresses changent à chaque modification. On peut s'en servir comme référence (MIT : crédit obligatoire), pas tel quel.

FE Maker compile la décomp : la séparation se fait directement dans le code C du moteur, ce qui est plus simple et plus propre qu'un patch.

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
