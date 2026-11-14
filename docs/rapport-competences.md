# Rapport : nos compétences, la liste de Mangs et les jeux officiels (ticket #70, 13/11/2026)

## En bref

- **Pourquoi elles diffèrent** : la liste de Mangs vient du **Skill System FE8 classique** (l'ancien, en assembleur, numéros de compétence en hexadécimal, environ 255 places), adapté pour son hack « chat picks ». Nos compétences viennent du **C-SkillSys** de Mokha, son successeur réécrit en C sur les noms de la décomp : environ 530 compétences, souvent les mêmes, parfois rééquilibrées ou renommées. C'est le seul qu'on peut reprendre presque tel quel dans la décomp (`docs/competences.md`).
- **Chiffres** : Mangs liste 239 compétences ; on en a 223, plus nos capacités du jeu (Canto, Vol, Crochetage, Crit +15, Silencieux…).
  - **146** de ses compétences sont chez nous (parfois sous un autre nom : Miracle = Inori, Inspiration = Inspir, Voice of Peace = V-Peace, Infiltrator = Infilt, Crit Boost = Crit +15, Lethality = Silencieux…) ;
  - **74** sont dans le C-SkillSys mais pas encore portées (liste plus bas) ;
  - **19** n'existent pas dans le C-SkillSys (à écrire nous-mêmes ou à laisser).
- **Les nombres diffèrent parfois** pour une même compétence : par exemple Defiant +4 chez Mangs, +7 dans le C-SkillSys ; Death Blow +6 Atk chez lui (et un second Death Blow à +20 critique). On garde les valeurs du C-SkillSys ; un réglage des nombres par compétence est possible plus tard.
- **77 de nos compétences ne sont pas chez Mangs** : bonus de stats (+2), Push (+5 à PV pleins), « Fighter » de Fates (Quick Riposte, Bold Fighter…), Crit/Avoid par arme, Faire pour Anima / Lumière / Ténèbres, Boost des éléments, Analytic, Heavy Blade, Flashing Blade, No Guard, Wonder Guard, Dragon Skin, Multiscale, Barricade, Inner Flame, Shade+, Provoke, etc.

## Ses compétences qui nous manquent

### Dans le C-SkillSys, à porter (74)

| Famille | Compétences | Ce qu'il faut |
| :-- | :-- | :-- |
| Breakers | Swordbreaker, Lancebreaker, Axebreaker, Bowbreaker (Tomebreaker = BMagBreaker) | **faites (lot 10, 13/11)** |
| Rally (commande) | Rally Strength, Magic, Skill, Speed, Luck, Defense, Resistance, Movement, Spectrum | **faites (lot 10, 14/11)** sauf Movement ; Magic avec Force et Magie séparées |
| Sceaux après combat | Seal Attack (SealStrength), Magic, Skill, Speed, Luck, Defense, Resistance | **faits (lot 10, 13/11)** |
| Après le combat | **faites (lot 10, 13/11)** : Fury, Grisly Wound, Poison Strike, Breath of Life, Lifetaker, Despoil. puis le 14/11 Savage Blow, Lunge, Devil's Pact / Luck / Whim | effets après le combat (`BattleUnwind`), à faire en un lot |
| Commandes de carte | Smite, Pass, Supply | **faites (lot 10, 14/11)** ; Supply était déjà la compétence du jeu |
| Croissances et expérience | Paragon, Blossom, Aptitude, Discipline | **faites (lot 10, 14/11)** |
| Déclenchements | Great Shield, Sure Shot, Deadeye, Killing Machine, Counter, Countermagic, Nihil, Nullify, Hero, Rightful King, Rightful God | faits le 14/11 (lot 10) sauf Nihil ; Great Shield et Sure Shot sont celles du jeu |
| Passives | **faites (lot 10, 13/11)** : Life and Death, Light Weight, Elbow Room, Critical Force, Battle Veteran, Loyalty, Blue Flame, Outdoor Fighter ; le 14/11 Resolve, Lucky Seven, Triangle Adept, Skybreaker, Slayer (celle du jeu, attribuable). Restent : Thunderstorm, Celerity (MovBonus, déplacement) | moyennes : touchent aux calculs du jeu |
| Portée des armes | Point Blank, Staff Savant | lot 9 suite (portée), reporté « plus tard » |
| Déplacement, tour | Keep Up, Armor March, Nature Rush, Boon, Powerstaff | début de tour et déplacement (lot 9 suite) |
| Divers | Bargain (prix des magasins), Axefaith | faites le 14/11 (lot 10), avec Deal |

### Absentes du C-SkillSys (19)

Vantage+, Steal+, Re-Move, Shadowgift, Lumina, Recklessness, Tome Range +1, Acrobat, Certain Blow (proche de notre Uncanny Blow), Insight, Inspiring Tune, Assassinate, Savior, Live to Serve, Discipline+, Gamble, Full Metal Body, Liquid Ooze, Indoor Fighter.
La plupart sont des variantes simples d'autres compétences (Insight = +20 précision, Recklessness = +5 / -5…) : faciles à écrire si tu les veux. Shadowgift et Lumina (utiliser une magie qu'on n'a pas) touchent aux rangs d'armes ; Re-Move et Steal+ sont plus lourdes.

## Les jeux officiels

Lu sur le wiki (page « Skills ») : seule la présentation par jeu ; les listes complètes de chaque jeu sont sur des pages à part, que je n'ai pas relues une à une. Le reste vient de ma connaissance des jeux.

- **FE4 et FE5** : Sol, Luna, Astra, Adept, Vantage, Wrath, Miracle, Pavise, Nihil, Charm, Renewal, Steal, Dance… presque toutes présentes chez nous ou dans la liste à porter.
- **FE8 (le jeu de base)** : les compétences y sont des capacités de classe : Canto, Vol, Crochetage, Crit +15, Silencieux sont attribuables chez nous. **Perce, Grand bouclier, Coup sûr, Tueur et Invocation** sont liés à des classes précises dans le code du jeu : on ne peut pas encore les donner à n'importe qui (Great Shield, Sure Shot et Slayer existent dans le C-SkillSys, voir plus haut).
- **FE9 et FE10 (Tellius)** : Paragon, Blossom, Discipline, Celerity, Resolve, Corrosion, Provoke, Shove, Parity, Cancel, Guard, Gamble, Saviour, et les compétences de maîtrise (Lethality, Colossus, Stun, Roar, Eclipse, Impale…). La plupart sont chez nous ou à porter ; Parity, Cancel, Guard, Stun et Roar n'y sont pas.
- **FE13 et FE14 (Awakening, Fates)** : c'est la source principale des deux listes (Breakers, Faire, Galeforce, Aether, Lethality, Rally, Counter, Pass, Acrobat, Vantage, Lifetaker, les « Fighter » et « Stance » de Fates). Restent hors de portée : tout ce qui touche au duo (Dual Strike, Dual Guard, Pair Up), et les compétences propres à un personnage dont l'effet est unique.
- **FE15 à FE17 (Echoes, Three Houses, Engage)** : beaucoup de bonus simples (Avoid +10, Prowess, Faire, Breakers, Death Blow, Fiendish Blow) déjà là. Leurs systèmes (arts de combat, gambits, bataillons, Emblèmes) ne vont pas dans un moteur GBA.

## Ce que je propose

1. **Un lot 10 « liste de Mangs »** : porter du C-SkillSys les 74 qui y sont, par familles, dans l'ordre du tableau (breakers et passives d'abord, puis après le combat et sceaux, puis croissances, puis Rally et commandes). Environ 2 à 3 lots comme les précédents.
2. **Capacités du jeu** : rendre attribuables Supply, Dance / Play, Summon et Magic Seal (bits du jeu déjà là, peu de travail).
3. **Les 19 absentes** : seulement celles que tu veux ; les variantes simples se font en même temps que le lot 10.
4. **Les nombres** : garder ceux du C-SkillSys, et plus tard un réglage des valeurs par compétence dans FE Maker (comme les nombres de Mangs).
