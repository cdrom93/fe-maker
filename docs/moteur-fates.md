# Autres moteurs : Fates (3DS), puis Switch

Idée de l'utilisateur (08/11/2026), à long terme : une fois FE Maker GBA assez avancé, le décliner pour d'autres moteurs,
d'abord celui de Fates (jeux au format 3DS), plus tard un jeu Switch / Switch 2. Pas d'autre moteur GBA prévu (FE6, FE7 : non, son choix).
Rien n'est commencé ; à concevoir avec lui.

## Ce qu'on a trouvé (recherches du 08/11/2026)

### Recompilations : pour faire tourner le jeu, pas pour l'éditer

| Projet | Jeu | Licence | Ce que c'est |
| --- | --- | --- | --- |
| [3dsrecomp](https://github.com/fearkov/3dsrecomp) (fearkov) | n'importe quel jeu 3DS | aucune : code non réutilisable | recompilateur statique ARM11 → C |
| [Zakuro](https://github.com/fearkov/zakuro) (fearkov) | idem | MIT | émulateur 3DS (Rust) qui exécute le code recompilé ; Fates « Special Edition » USA « Playable » dans sa liste de compatibilité (le post de l'auteur parle encore de bugs) |
| [FE3H Recomp](https://gitlab.com/onerag90/fe3h-recomp) (onerag90, d'après LAS Recomp de Peiikai) | Three Houses (Switch) | MIT | recompilation statique en programme Windows (Vulkan), jouable ; demande les fichiers du jeu |

Aucun ne documente les données du jeu (personnages, classes, chapitres, forge, base). FE Maker repose sur une décomp lisible
(sources C, tables, scripts d'évènements) : une recompilation ne la remplace pas. Usage : observer le jeu en marche (forge, château
de Fates, monastère de Three Houses) et, peut-être, tester un mod sur PC.

### Outils de modding de Fates : la vraie base

Aucune décomp de Fates trouvée. Les outils existants lisent et réécrivent les fichiers du jeu, ce qui est proche de ce que fait FE Maker :

| Outil | Licence | Rôle |
| --- | --- | --- |
| [Paragon](https://github.com/thane98/paragon) (thane98) | GPL-3.0 | éditeur des données de FE13 à FE15, Fates le mieux couvert (successeur de FEFEditor et FEFNightmare) ; mis à jour en 2026 |
| [Exalt](https://github.com/thane98/Exalt) (thane98) | GPL-3.0 | compilateur / décompilateur des scripts d'évènements des FE 3DS |
| [FEAT](https://github.com/SciresM/FEAT) (SciresM) | GPL-2.0 | extraction des archives des FE 3DS |
| [FEST](https://github.com/RainThunder/FEST) (RainThunder) | — | compression / décompression des sauvegardes d'Awakening et Fates (secondaire) |

Licences compatibles avec FE Maker (GPL), à créditer dans `CREDITS.md` le jour où on s'en sert.

### Hacks de Fates (répertoire des fangames de FEU)

[Répertoire](https://feuniverse.us/t/the-fire-emblem-fangame-directory-please-add-your-own-hacks/3339), section FE14 : surtout des
rééquilibrages du jeu d'origine (Upgraded, Stoneborn Emblem, Gen 2, Final Mix Redux), faits avec ces éditeurs. Rien à reprendre
tel quel (données de Fates, pas de licence libre) ; utiles comme exemples de ce que Paragon permet. Idées d'outils qui
vaudraient aussi pour FE Maker GBA (pas encore retenues) : échanger deux personnages partout (les « Reverse Recruitment »
d'Itranc), changer les classes d'un groupe en lot (« Heart Seal Class Swap »), option de triangle des armes inversé (« Weapon Reversal »).

## Voie envisagée

- Un moteur à la fois, chacun un gros chantier (presque un nouveau FE Maker côté données).
- Fates : s'appuyer sur les formats que Paragon et Exalt savent lire et écrire ; sortie en mod (LayeredFS) appliqué au jeu
  d'origine, sur console modifiée ou émulateur, pas un jeu recompilé.
- Dès maintenant : garder l'interface et le format de projet sans hypothèse FE8 inutile, la lecture de la décomp isolée dans
  `server/fe_maker/decomp/`.
