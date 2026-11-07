# Compétences (portage du C-SkillSys dans la décomp)

Décidé avec l'utilisateur le 06/11/2026 : on porte les compétences du C-SkillSys dans le code de la décomp, comme la séparation force / magie (`strmag.py`). On n'intègre pas le C-SkillSys entier (voir `docs/separation-force-magie.md` : il vise la ROM d'origine, réécrit tous les textes et plusieurs tables).

## Source

- [fe8u-cskillsys-kernel](https://github.com/MokhaLeee/fe8u-cskillsys-kernel) (MIT ; Mokha, avec Jester, AliScrooge, Vesly ; StanHash, laqieer, Eebit, Revo remerciés), en C sur les noms de la décomp : ses fonctions remplacent celles du jeu (`LYN_REPLACE_CHECK`), on peut donc reprendre son code presque tel quel dans l'overlay.
- Ce qu'on reprend :
  - le testeur de compétences (`SkillTester`, `BattleFastSkillTester`, `Kernel/Wizardry/Core/SkillSys/kernel`) ;
  - les effets compétence par compétence (`Kernel/Wizardry/Core/BattleSys/Source/PreBattleCalc.c`, `BattleOrder.c`, `BattleHit.c`, `Kernel/Wizardry/Misc/SkillEffects`) ;
  - les noms et les descriptions (`docs/SkillInfo.md`, `Data/SkillSys/Source/SkillInfo.c`) ;
  - les icônes (`Contents/Gfx/Sources/SkillIcon`, 421 images).
- Crédits : la ligne C-SkillSys de `CREDITS.md`, complétée à chaque lot. Les icônes viennent de leurs artistes (GratedShtick, JeorgeReds et ceux du Skill System). Chaque compétence garde l'auteur de son idée quand on le connaît (Skill System d'origine, jeux officiels).
- Les icônes ne vont jamais dans le dépôt : elles sont téléchargées au premier usage, au commit fixé, comme la décomp.

## Principes

- **Activation** : option du jeu « Compétences » (catégorie Règles), cochée d'office dans un nouveau projet. Seules les compétences utilisées sont compilées. Un projet sans compétence redonne la ROM d'origine.
- **Catalogue** : il est dans FE Maker (`server/fe_maker/decomp/skills.py`). Chaque compétence a :
  - un nom anglais repris du C-SkillSys ;
  - son effet, en C ;
  - son icône ;
  - son nom et sa description en français et en anglais, qui deviennent des textes du jeu modifiables.
- **Numérotation** : les compétences utilisées sont numérotées 1 à N à la compilation.
- **Projet** :
  - les fiches personnage et classe ont leurs compétences (3 au plus chacune, comme le C-SkillSys) ;
  - viendront ensuite les objets et les armes (compétence tant que l'objet est porté ou équipé).
- **Moteur** :
  - tables `gCharacterSkillsFem` et `gClassSkillsFem` ;
  - `SkillTesterFem(unit, n)` sur l'unité, la `BattleUnit` passant par son unité ;
  - les effets écrits aux endroits où le C-SkillSys les écrit (calculs avant le combat, ordre des coups, coups).
- **Affichage** :
  - fiche de l'unité, page 1 : les icônes des compétences, avec leur nom et leur description sur R ;
  - au combat : le nom de la compétence quand elle se déclenche (lot 2).

## Lots

1. **Noyau et compétences passives** :
   - Moteur :
     - le testeur ;
     - les tables par personnage et par classe ;
     - les icônes et l'aide R sur la fiche.
   - Une vingtaine de compétences passives :
     - bonus de stats (PV, For, Mag, Tec, Vit, Cha, Déf, Rés, Dépl.) ;
     - « Défiant » (+7 sous 25 % de PV) ;
     - coups à l'attaque (Darting, Death, Armored, Warding Blow) ;
     - Wrath ;
     - Vantage ;
     - Desperation.
   - FE Maker :
     - le catalogue dans une liste ;
     - le choix sur les fiches personnage et classe.
   - Vérifié en jeu par playtest.
   - **État (06/11/2026)** : fait et vérifié par playtest (`tests/local` : bonus en combat, ordre des coups, fiche et aide R), pas encore vu en jeu par l'utilisateur. Commit d'origine `fb545870458f3c3629cab6cfb2330c3308d2ce6d` ; repris de :
     - testeur et tables : `Kernel/Wizardry/Core/SkillSys/kernel` (3 compétences par personnage et par classe) ;
     - bonus de stats et Sursaut de stats : `Kernel/Wizardry/Core/UnitStatusGetter/source/*Getter.c` ;
     - Sursaut (critique, esquive), coups, Colère : `Kernel/Wizardry/Core/BattleSys/Source/PreBattleCalc.c` ;
     - Initiative et Désespoir : `Kernel/Wizardry/Core/BattleSys/Source/BattleOrder.c` ;
     - textes du jeu : `Contents/Texts/Source/texts` (celui de Désespoir réécrit) ; icônes : `Contents/Gfx/Sources/SkillIcon` (Perce prend l'icône de Luna, absente sinon).
   - Écarts : les bonus de PV, de constitution et de déplacement prévus ne sont pas faits (pas de getter simple dans le jeu) ; les textes du jeu restent en anglais ; la fiche montre 4 icônes au plus.
2. **Compétences à déclenchement** : Luna, Sol, Pavise, Adept, Aether…
   - **État (06/11/2026)** : 8 faites, vérifiées par playtest pour Luna et Sol (`tests/local`) : Luna, Corona, Sol, Éther, Ignis, Colosse, Pavois, Égide. Repris de `Kernel/Wizardry/Misc/SkillEffects/BattleDamage/AttackerSkills.c` et `DefenderSkills.c`, taux de `Misc/SkillActRate.c` (la technique en %, jamais dans l'aperçu du combat), au même commit. Dans `BattleGenerateHitAttributes` du jeu : avant les dégâts (défense, attaque, Pavois et Égide), après le critique (Colosse), et le soin de Sol et d'Éther à la place de celui de Nosferatu.
   - Affichage : pas de nom à l'activation pour l'instant ; les effets du jeu servent de signe (Luna et Corona comme Perce, Pavois et Égide comme Grand bouclier, Colosse comme un critique, Sol et Éther comme Nosferatu). À voir en jeu par l'utilisateur, surtout le soin de Sol avec une arme physique en animation de combat.
   - Adepte et Astra (06/11) : repris de `GetBattleUnitHitCount` (`BattleOrder.c`), vérifiés par playtest. Le jeu ne garde que 7 entrées de coups par combat (6 coups et la fin, tableau à adresse fixe) : un assaut s'arrête quand le tableau est plein (le C-SkillSys agrandit ce tableau ; pas nous). Astra ne joue que pour l'unité qui engage, chance = vitesse en %.
   - Nom au déclenchement (06/11), d'après la capture de l'utilisateur : en animation de combat, le nom et l'icône de la compétence glissent sous la plaque du nom de l'unité, restent 2 s et repartent. Repris du `SkillProcDisplay` de Huichelaar (Skill System, CC0 ; son image de fond téléchargée comme les icônes), lancé là où le jeu joue ses propres effets (commande C07) ; la compétence est notée avec son coup à la mémoire libre. Montre aussi Coup sûr, Perce et Grand bouclier du jeu. Ticket 170 : une compétence de l'attaquant sans effet du jeu (Sol, Éther, Ignis, Colosse, Astra) joue le flash et le son de Coup sûr, comme le Skill System (Luna garde celui de Perce, Pavois et Égide celui de Grand bouclier) ; la palette du côté gauche n'est plus écrasée. Vérifié par playtest (Luna, Sol). Sans animation de combat : l'icône de la compétence s'ouvre à côté de la boîte de combat sur la carte, 30 images (`SPD_Map` de Huichelaar, avant chaque coup dans `MapAnim_PrepareNextBattleRound`), playtest (Sol). Lot 2 terminé.
   - Taux selon la Technique, comme dans le C-SkillSys.
   - Nom affiché à l'activation, sur la carte et en combat.
3. **Compétences apprises** :
   - par niveau ou par promotion (listes du C-SkillSys) ;
   - commandes d'évènement pour donner ou retirer une compétence ;
   - parchemins ;
   - sauvegarde dans la zone libre de la mémoire (`SRAM_OFFSET_XMAP`, voir `docs/audit-decomp.md`).
   - **Plan (07/11/2026)**, étudié sur le C-SkillSys (`SkillSys/kernel/LearnSkill.c` : un bit par personnage et par compétence, sauvegardé avec la partie ; puis un écran d'équipement en préparation, mis à plus tard) :
     1. Liste apprise par personnage : 4 compétences au plus (numéros du projet), actives d'office (pas d'équipement), en plus de celles de sa fiche et de sa classe. En mémoire vive : 0x40 personnages × 4 octets à 0x02028800, dans le tampon de débogage libre (avant la table des icônes). Remise à zéro en nouvelle partie. `SkillTesterFem`, la fiche (page 1) et l'aide R la lisent.
     2. Sauvegarde : comme la magie (`strmag.py`), dans la zone des cartes bonus, à +0x480 : par emplacement (3 parties, 2 sauvegardes de mi-chapitre), l'heure de la sauvegarde puis la table (0x104 octets ; 5 × 0x104 = 0x514, jusqu'à +0x994 sur 0xC00). Une sauvegarde sans table (faite avant) : liste vide.
     3. Apprentissage par niveau : sur la fiche personnage et la fiche classe, « apprend X au niveau N » (comme les listes du C-SkillSys `SkillTable-person.c` / `-job.c`), au moment de la montée de niveau, avec le nom affiché. 5e compétence apprise : la plus ancienne est oubliée (le C-SkillSys garde tout, mais il a l'écran d'équipement).
     4. Commandes d'évènement « Donner une compétence » / « Retirer une compétence » (un personnage, une compétence).
     5. Parchemins : plus tard, avec les objets à effet.
     - Joueur seulement (comme le C-SkillSys : un ennemi n'apprend rien) ; vérifié par playtest (sauvegarde, rechargement, montée de niveau).
     - **État (07/11/2026)** : points 1 et 2 faits (`LearnSkillFem` / `ForgetSkillFem` dans `bmunit.c`, table remise à zéro par `InitPlayConfig`, écrite et relue aux 4 endroits où le jeu sauve ses unités, copiée avec une partie) ; playtest : une compétence écrite dans la table compte en combat. Sauvegarde et rechargement pas encore vus en jeu. Points 3 et 4 faits le 07/11 : `LearnLevelSkillsFem` après chaque montée de niveau et promotion (fiches personnage et classe, « Apprises par niveau », 4 au plus) ; commandes d'évènement « Donner / Retirer une compétence » (`FemSkillEvent`, emplacements 1 à 3 + ASMC). Playtest : Str+2 appris au passage au niveau 2. Message « X learned [icône] Y. » après le combat, le bâton, la danse ou l'arène où la compétence est apprise (vu par playtest) ; commandes d'évènement pas vues en jeu.
4. **Compétences de carte et de menu** : Canto, Renewal, Galeforce, Steal, Dance…, et l'IA qui en tient compte.
   - **Plan (07/11/2026)** :
     1. Capacités du jeu en compétences attribuables : le jeu les teste partout par `UNIT_CATTRIBUTES` (`bmunit.h`, ~90 appels, IA comprise : vol, crochetage). Le redéfinir en `... | SkillAttributesFem(unit)`, qui rend les bits `CA_*` des compétences du jeu présentes dans les listes du personnage, de sa classe et ses compétences apprises (pas par `SkillTesterFem`, qui relit `UNIT_CATTRIBUTES` pour les compétences du jeu : boucle). D'abord Canto, Vol, Crochetage, Crit +15, Létalité ; Danse et Invocation plus tard (animation de danse de la classe, tables d'invocation).
     2. Nouvelles compétences de carte, d'après le C-SkillSys (`PostActionSkills/Canto.c`, `PrePhaseSkills/PrePhaseHeal.c`, Galeforce) : Canto+ (bouger après un combat ou un bâton), Renewal (PV +30 % au début du tour), Galeforce (rejouer après avoir vaincu un ennemi, une fois par tour).
     3. Commandes de menu (Steal du C-SkillSys, `MenuSkills/`). Étude du 07/11 : le C-SkillSys ajoute ses commandes au menu d'unité (`gUnitActionMenuItems`, `menu_def.c` : nom et aide en numéros de message, `Usability`, `Effect`), choisit la cible avec `NewTargetSelection` et un `SelectInfo`, puis joue un type d'action à lui (`CONFIG_UNIT_ACTION_EXPA_ExecSkill`, après `UNIT_ACTION_EXIT_BALLISTA` = 0x22) traité dans `ApplyUnitAction` (`bmmind.c`). Ordre prévu : Pivot (passer de l'autre côté d'un allié adjacent), Repositionnement (faire passer l'allié derrière soi), Bousculade (pousser d'une case) et Échange (`HerosMovement/`, code commun `HmuCommon.c`) : une seule entrée de menu par compétence, textes ajoutés par `add_texts`, déplacement par le MU du jeu. **Pivot fait le 07/11** (`_menu_skills` : entrée avant Porter, cible choisie, puis l'unité « se déplace » là et attend, sans animation de glissement ; playtest). Puis, au-delà des capacités du jeu, à voir après 1 et 2.
     4. Playtests : Canto donné à un fantassin, vol par une unité non voleuse, Renewal au début du tour.
   - **État (07/11/2026)** : point 1 fait (`ASSIGNABLE` dans `skills.py`, groupe « Capacités du jeu » des fiches ; `UNIT_CATTRIBUTES` n'est redéfini que si une fiche ou un évènement en donne une). Playtest : Crit +15 donné au seigneur, critique = Tec / 2 + 15. Canto, Vol, Crochetage et Létalité passent par le même chemin, pas vus en jeu un par un (le Canto du jeu ne joue pas après Attendre, un combat ou un bâton : seulement après échanger, porter, objet...).
     Point 2 fait le 07/11 (`_map_skills`, chacune ajoutée seulement si le projet s'en sert) : Canto+ (le Canto du jeu, aussi après un combat ou un bâton), Renouveau (+30 % des PV max avec le soin du terrain, `MakeTerrainHealTargetList`), Bourrasque (après un combat gagné, l'unité rejoue, une fois par tour, à Tec % ; avant le Canto dans `PlayerPhase_FinishAction`). Playtest : Renouveau 1 → 5 PV sur 16, Bourrasque : l'unité reste active ; Canto+ : l'unité repasse en déplacement après un combat. Restent : commandes de menu (point 3), l'IA (Bourrasque et Canto+ pour le joueur seulement, comme le Canto du jeu ; Renouveau pour tous).

Plus tard :
- les arts de combat ;
- l'équipement des compétences en préparation (comme dans FE16) ;
- les compétences d'objets et d'armes ;
- l'import de ses propres icônes.

## Choix de l'utilisateur (06/11/2026)

- **Capacités de classe du jeu** : Perce, Grand bouclier, Coup sûr, Silence, Tueur, Vol et Canto sont montrées comme des compétences, avec leurs icônes, sur la fiche de l'unité et dans FE Maker.
- **Compétences de classe par défaut (06/11)** : comme dans FEBuilder (table `ClassSkillTable` du Skill System : Canto des montés, Grand bouclier du Général, Coup sûr du Sniper, Crit +15 du Bretteur, Invocation, Cunning des voleurs, Slayer de l'Évêque, Supply des seigneurs). Toutes sont des comportements du jeu d'origine : FE Maker les montre déjà comme compétences du jeu, plus Approvisionnement pour le seigneur de la route (Eirika ou Ephraim, par personnage comme `SupplyUsability`) et Tueur pour l'Évêque (`IsUnitEffectiveAgainst`). Cunning = Vol + Crochetage chez nous. Rien à remplir dans les fiches de classe.
- **Présentation sur la fiche** : celle du Skill System (MSS), d'après sa capture.
  - Colonne de droite de la page 1, le mot « Skills » centré, les icônes en dessous.
  - Chez nous, sous « Cond » : rangées 13 et 15, libres même avec force et magie séparées.
- **Ticket 171 (06/11), 6 compétences sur la page 1**, d'après sa capture (hack de l'arène de Mangs, base MSS ; la page 1 « Page1WithLeadership » du C-SkillSys, `Kernel/Wizardry/Core/StatScreen/DrawUnitPage/PlanB`, en est proche mais met les compétences sur une autre page). Ses choix :
  - colonne de gauche : For, Mag, Tec, Vit, Cha, Déf, Rés, puis Dépl. (rangée 15 ; 13 sans la séparation force / magie) ;
  - colonne de droite, comme la capture (son choix revu le 06/11) : Con, Aid, Cond, Lead, Talk (avec qui l'unité peut parler, lu comme le C-SkillSys le fait pour `gStatScreenStExpa.talkee`), puis « Skills » et 2 rangées de 3 icônes, sans cadre ; Trv (unité portée) quitte la page ;
  - Affin : son icône passe à droite du nom (panneau de gauche), comme sur la capture ; aujourd'hui elle est dans la colonne de droite ;
  - Lead : « -- » par défaut ; le commandement (étoiles du C-SkillSys, `GetUnitLeaderShip` : une valeur par personnage et son bonus en combat) viendra en option du jeu, dans une catégorie (sa demande du 06/11), après la page ;
  - aide R sur les 6 icônes.
  - **État (07/11/2026)** : fait, vérifié par playtest (`tests/local`, fiche et aide R sur la 4e compétence). Talk repris du `GetTalkee` du C-SkillSys (`DrawUnitPage/Source/Util.c`) : évènement de dialogue du chapitre, puis soutien possible ; Lead affiche « --- » (texte d'aide : pas d'effet pour l'instant). En mode croissances (Select, #166), la ligne des PV prend la place de Dépl. À valider par l'utilisateur en jeu ; Talk pas vu en jeu sur un vrai dialogue.

## Suivre le C-SkillSys et ses auteurs

- **Licence** :
  - Le code repris reste sous MIT. Cette licence demande de garder son texte avec toute copie : il est dans `licenses/cskillsys-MIT.txt`.
  - FE Maker, en GPL-3.0, peut inclure du code MIT.
- **Commit d'origine** : chaque compétence portée note le commit et le fichier du C-SkillSys d'où elle vient.
- **Mises à jour** :
  - Un outil (`tools/cskillsys_watch.py`) liste ce qui a changé en amont depuis ce commit dans les fichiers repris.
  - On reporte les corrections à la main, compétence par compétence.
  - Rien n'est suivi automatiquement : le portage est une copie adaptée, pas une dépendance.
- **Participation des auteurs** :
  - Le dépôt public accepte leurs contributions, qui deviennent GPL-3.0 dans FE Maker (leur propre dépôt reste MIT).
  - Dans l'autre sens, on peut leur rendre nos adaptations à la décomp sous MIT, s'ils veulent une version du C-SkillSys pour la décomp. laqieer, remercié par le C-SkillSys, travaille déjà sur la décomp dans son fork de FEBuilder.
  - À faire avant l'annonce de l'alpha, par l'utilisateur : prévenir Mokha et les contributeurs du portage, leur montrer les crédits et proposer de participer.
