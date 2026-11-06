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
   - Reste : Adept et Astra (coups en plus, ordre des coups), le nom affiché au déclenchement (sur la carte et en combat).
   - Taux selon la Technique, comme dans le C-SkillSys.
   - Nom affiché à l'activation, sur la carte et en combat.
3. **Compétences apprises** :
   - par niveau ou par promotion (listes du C-SkillSys) ;
   - commandes d'évènement pour donner ou retirer une compétence ;
   - parchemins ;
   - sauvegarde dans la zone libre de la mémoire (`SRAM_OFFSET_XMAP`, voir `docs/audit-decomp.md`).
4. **Compétences de carte et de menu** : Canto, Renewal, Galeforce, Steal, Dance…, et l'IA qui en tient compte.

Plus tard :
- les arts de combat ;
- l'équipement des compétences en préparation (comme dans FE16) ;
- les compétences d'objets et d'armes ;
- l'import de ses propres icônes.

## Choix de l'utilisateur (06/11/2026)

- **Capacités de classe du jeu** : Perce, Grand bouclier, Coup sûr, Silence, Tueur, Vol et Canto sont montrées comme des compétences, avec leurs icônes, sur la fiche de l'unité et dans FE Maker.
- **Présentation sur la fiche** : celle du Skill System (MSS), d'après sa capture.
  - Colonne de droite de la page 1, le mot « Skills » centré, les icônes en dessous.
  - Chez nous, sous « Cond » : rangées 13 et 15, libres même avec force et magie séparées.

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
