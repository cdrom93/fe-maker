# Patchs de confort (QoL) à proposer dans FE Maker

Ticket 32 (24/10/2026). Source : la liste d'UltraxBlade sur FEUniverse (« What are the FEBuilder patches considered QoL? », reprise dans sa FAQ FEBuilder), rapprochée des patchs FE8U de FEBuilderGBA (dépôt `FEBuilderGBA-patch2`, dossier `FE8U/`, 509 dossiers, 1927 fichiers `PATCH_*.txt`, lu le 24/10/2026). Le nom entre crochets est le dossier et le fichier `PATCH_` du patch dans FEBuilder.

## Comment les faire dans FE Maker

FEBuilder pose ses patchs sur la ROM compilée, à des adresses fixes (crochets dans le code, `ORG`). FE Maker compile la décomp : les adresses bougent dès qu'on change quelque chose, donc **un patch FEBuilder ne peut pas être posé tel quel**. Trois façons, de la plus simple à la plus lourde :

1. **Réglage dans le code C de la décomp** (comme les modes de test, `tweaks.py`) : une constante, une condition ou une valeur par défaut. La plupart des patchs « SYSTEM » de FEBuilder sont de ce genre (quelques octets). C'est la voie à privilégier : le patch FEBuilder sert de cahier des charges, on écrit le changement en C.
2. **Petite routine en C ajoutée** : affichages (barres de PV, soins des bâtons), menus. Le patch FEBuilder (souvent un source Event Assembler / ASM fourni avec) sert de référence ; on réécrit en C.
3. **Gros systèmes** (Skill System, séparation force/magie, boîte d'infos modulaire) : il existe une version **pour la décomp** du Skill System, *C-SkillSys* (FEBuilder en a les versions `skill20240910-CSkillSys100LTS` et `skill202501220-CSkillSys330LTS`), écrite en C sur la décomp FE8U. C'est la bonne base pour la séparation force/magie (ticket 27) et les compétences, à intégrer comme une option du projet plutôt que patch par patch. Licence à vérifier avant toute reprise.

Licences : le code de FEBuilderGBA est en GPL-3.0 ; les patchs viennent d'auteurs de FEU, chacun avec ses conditions (souvent indiquées dans le dossier du patch). Avant de reprendre le code d'un patch, lire ses conditions et le créditer dans `CREDITS.md`. Réécrire le comportement en C d'après sa description ne reprend pas son code.

## Priorité 1 : confort sans effet sur le jeu (à proposer cochés par défaut)

| Patch | Dans FEBuilder | Réalisation dans FE Maker |
|---|---|---|
| Pas de zone de déplacement pour les ennemis immobiles (IA « ne bouge pas ») — le plus important selon l'auteur | `Null Move Display-7743` | C : ne pas dessiner la zone de mouvement d'une unité dont l'IA ne bouge pas |
| Barres de PV sur les sprites de carte, avec alertes armes efficaces / critiques | `HPbars`, `HPbars_simple`, `HpBars_Cache` | C : routine d'affichage sur la carte |
| Chiffres du combat quand les animations sont coupées | `FE8-Battle Stats with Anims Off(v2)` | C |
| Afficher les PV soignés par un bâton | `Show Heal Amount` | C |
| Vitesse du texte « rapide » par défaut, curseur automatique coupé par défaut | réglages par défaut des options (SYSTEM) | C : valeurs initiales des options d'une nouvelle partie |
| Passer l'avertissement de santé, les logos et l'animation d'ouverture | `SYSTEM/OPENING_CUT`, `SYSTEM/SKIP_OPENING`, `Mode Coefficient EXP fix/Skip H_S screen`, `Skip Intro cutscene` | C : FE Maker a déjà la mécanique (modes de test « au menu », « sur la carte ») ; en faire une option du jeu final |
| Option de jeu : animations des bâtons et des danses coupées | `SYSTEM/Dance animation off`, `ForceBattleOffWithDanceAndStaff`, `SYSTEM/Staff that ignores battle animation` | C |
| Statistiques des armes de monstre | `SYSTEM/Monster Weapon display fix` | C |
| R pour accélérer, L pour passer les animations de combat | `SpeedUpAnims`, `FastBattleAnimation` | C ; L accélère déjà (`holdLBattleSpeed`). Reporté : l'utilisateur veut que le créateur choisisse les touches (cahier, idées, 09/11) |
| Écrans plus rapides : titre de chapitre sans attente d'une seconde, combats sur la carte sans délai, barre d'expérience rapide | `SYSTEM/Omission of 1-second wait when displaying chapter titles`, `Remove delay at start of map battle`, `Remove Round delay in map battle`, `Display bar quickly when getting exp in map anime`, `Acceleration of growth status display of level up` | C : constantes de durée |
| A maintenu accélère les déplacements | `Mode Coefficient EXP fix/Hold A to speed up movement` | C |
| Correctifs de bugs du jeu d'origine (#ESSENTIAL dans FEBuilder) | `BattleForecastFix`, `FE8-Staff Range Fix`, `Enemy Control Glitch Fix`, `MNC2Fix`, `HP Bar and Cloud Fix`, `FillAIDangerMap` (lenteurs de l'IA), `Fix_*`… | Option BUGFIX de la décomp (déjà prévue, désactivée par défaut) plus les correctifs un par un ; à trier |

## Priorité 2 : informations en plus (option, conseillée)

| Patch | Dans FEBuilder | Réalisation |
|---|---|---|
| Boîte d'infos au survol d'une unité (stats, inventaire) | `ModularMinimugBox`, `ModularMinimugBoxVer2` | C, plusieurs styles proposés comme dans FEBuilder |
| Croissances visibles sur la fiche d'unité, avec qui elle peut « Parler » | pas un patch FEBuilder seul (Insert EA) | C |
| Vrais nombres dans les descriptions d'objets (soin d'un Vulnéraire…) | pas un patch : texte | FE Maker : proposer les valeurs dans l'éditeur de descriptions |
| Mode Débutant (Casual) en option | `CasualMode`, `CasualMode_Gameoption`, `CasualModeMenu2.en` | C : les unités vaincues reviennent au chapitre suivant |
| Plusieurs marqueurs de sortie / repères sur la carte | `MultiTileMarker` | C, et un outil de l'éditeur de cartes |
| Zone de danger des ennemis (Select) | `Danger Zone` | **Fait** (`dangerZone`) : l'affichage du jeu lui-même, sans toucher aux palettes |
| Croissances sur la fiche d'unité (Select, ticket 166) | (Skill System, dans sa fiche réécrite) | **Fait** (`statusGrowths`) : page 1, croissances du personnage (+5 du Tome de Metis), barre jusqu'à 100 %, ligne PV sous Rés, magie avec la séparation |

## Priorité 3 : changements de règles appréciés (option, décochés)

| Patch | Dans FEBuilder | Réalisation |
|---|---|---|
| Convoi agrandi à 200 objets | `ExpandedModularSave_ExpandSupply` (fait partie de la sauvegarde modulaire étendue) | C : taille du convoi et format de sauvegarde (la décomp le permet sans patch de sauvegarde à part, à étudier) |
| Parler ne termine pas l'action | fait (option « Agir après avoir parlé ») | C |
| Soutien ne termine pas l'action | fait (même option) | C |
| Voler avec l'inventaire plein (l'objet part au convoi) | `StealWithFullInv` | C |
| Soutiens plus rapides ou autrement (portée, une fois par chapitre « façon FE9 ») | `SYSTEM/Change increases support level continuously even with one map`, `Gain support points by than adjacent`, `Change SupportLevel fot next level C/B/A` | FE Maker règle déjà les points par paire ; ajouter la portée et le mode « par chapitre » |

## Priorité 4 : changements qui demandent de concevoir les cartes autour (option, avec avertissement)

| Patch | Dans FEBuilder | Remarque |
|---|---|---|
| Échanges « Thracia » (plusieurs échanges dans la même action) | `SYSTEM/Thracia Rescue Trading AKA Infinite Give and Take` | change l'équilibre |
| Sauvegarde au début de chaque tour (revenir au début du tour) | `autosave`, `autosave_killer` | la version FEBuilder compatible avec le Skill System supprime la sauvegarde après chaque action |
| Déplacer les unités obligatoires pendant la préparation | `SYSTEM/Allow Forced Units to change their Starting Position` | FE Maker peut le faire par unité (une case « peut être déplacée ») au lieu de tout le jeu |

## Hors FEBuilder (Insert EA), à garder en tête

- *Danger Radius* et *Droppable Item Marker* (objets que lâchent les ennemis), version de Vesly avec les objets à voler.
- *Convoy Partition and Item Combination* (Tequila) : fusionner les objets en double en les rangeant (L).

## Fait (30/10/2026)

Onglet « Options du jeu » (`server/fe_maker/decomp/gameoptions.py`) : réglages d'une nouvelle partie (vitesse du texte, curseur, animations…), passer l'ouverture, titre de chapitre sans attente, A maintenu accélère dès la première partie, pas de zone de déplacement pour les unités immobiles (« Null Move Display »).

Ensuite : barres de PV sur la carte, mode débutant, barre d'expérience et gain de niveau rapides, ligne « Staff & Dance » sous « Animation » dans le menu Configuration du jeu.

## Ordre de travail proposé

1. Une page « Options du jeu » dans FE Maker (onglet ou section du projet) qui liste ces patchs par priorité, avec une description en français et la source.
2. Les patchs de priorité 1 qui sont des constantes (vitesse du texte, curseur, ouverture, délais) : quelques lignes de C chacun, compilés et vérifiés avec le playtest sans fenêtre.
3. Les affichages (barres de PV, chiffres des combats, soins, boîte d'infos).
4. C-SkillSys comme option du projet (séparation force/magie, compétences), après étude de sa licence et de son intégration au build.

## Lot suivant (choisi le 09/11/2026, d'après le guide QoL d'UltraxBlade sur FEU)

1. Alertes sur les barres de PV : un ennemi qui a une arme critique ou efficace contre l'unité choisie est signalé (comme `HPbars` de FEBuilder).
2. Statistiques des armes de monstre (`SYSTEM/Monster Weapon display fix`).
3. Correctifs « #ESSENTIAL » de FEBuilder : les trier un par un (bug du jeu d'origine ou simple avis), faire ceux qui corrigent un vrai bug, cochés d'office.
4. Ensuite : sauvegarde en début de tour en option réglable par le joueur ; unités obligatoires déplaçables unité par unité pendant la préparation.
