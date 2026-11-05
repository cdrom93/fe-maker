# FE Maker — Cahier des charges

> Ce que doit être FE Maker, où on en est, ce qu'il reste à faire. Si une décision change, on met ce fichier à jour **avant** de coder.
> Le fonctionnement du code est dans `docs/architecture.md`, l'historique dans `docs/journal.md` et git.

---

## 1. Vision

**FE Maker est un éditeur open source pour créer des jeux tactiques sur le moteur de Fire Emblem: The Sacred Stones (FE8, GBA), aussi simple à utiliser qu'un « RPG Maker ».**

En une phrase : *faire ce que fait FEBuilderGBA, mais en beaucoup plus facile à prendre en main.*

### Pour qui
- Le joueur qui veut créer son propre jeu ou une variante d'un jeu existant (ex. refaire FE7 avec ses propres règles), sans connaissances techniques.
- Le moddeur confirmé qui veut aller plus loin (modifier le moteur en C) sans quitter l'outil.

### Ce qui nous différencie de FEBuilderGBA
| FEBuilderGBA | FE Maker |
|---|---|
| Très complet, mais des centaines d'écrans et de réglages bruts (adresses, pointeurs, octets) | Peu d'écrans, organisés par **ce que l'utilisateur veut faire** (« créer un personnage », « faire un chapitre ») |
| Édite directement le binaire de la ROM | S'appuie sur la **décompilation FE8** : données lisibles, moteur modifiable en C, compilation reproductible |
| Windows uniquement | **Windows d'abord**, Linux et macOS ensuite (le code reste multiplateforme) |
| Ressources graphiques à chercher soi-même sur les forums | **Bibliothèque communautaire intégrée** (FE-Repo), avec licences et crédits gérés automatiquement |
| Vocabulaire technique | Vocabulaire de joueur, aide contextuelle, valeurs par défaut sensées, aperçus visuels partout |

### Principes d'ergonomie (non négociables)
1. **Jamais d'adresse mémoire, de pointeur ou d'hexadécimal visibles** dans le mode normal. Un « mode expert » peut les montrer.
2. **Un aperçu visuel pour tout** : portrait, sprite, carte, fiche de stats telle qu'elle apparaîtra en jeu.
3. **Assistants pas à pas** pour les tâches courantes (nouveau personnage, nouveau chapitre, nouvelle classe).
4. **Annuler / rétablir** partout. Sauvegarde automatique.
5. **Validation en direct** : l'outil empêche ou signale ce qui casserait le jeu (stat hors limite, ID en double, carte sans point de départ…) avant la compilation.
6. **Un seul bouton « Tester »** : compile et lance le jeu dans l'émulateur.
7. Interface **en français et en anglais** (fichiers de traduction).
8. **Tout ce qui est mentionné est cliquable** : une arme, une classe, un personnage, une liste… cité n'importe où (rappel, puce, liste déroulante, message d'erreur) ouvre directement sa fiche, sans aller-retour entre les onglets.
9. **Illustrer avec les visuels du jeu** : icônes d'armes et d'objets, portraits, sprites de carte, tuiles, avant tout emoji ou icône dessinée. Un emoji seulement s'il sert d'icône (outils de la carte, types d'objectif, repères ⚠ ⭐ ✎), jamais devant le texte d'un bouton, d'un lien, d'un titre ou d'une phrase.

---

## 2. Cadre légal et licences (à respecter strictement)

Le projet doit pouvoir vivre publiquement sur GitHub sans risque.

1. **Aucune donnée Nintendo dans le dépôt** : ni ROM, ni assets extraits, ni fichiers générés à partir de la ROM.
2. **L'utilisateur fournit sa propre ROM** (FE8 US, SHA1 `c25b145e37456171ada4b0d440bf88a19f4d509f`). L'outil refuse toute autre ROM avec un message clair.
3. **La décomp FE8 est un sous-module Git non modifié**, jamais copiée dans notre dépôt ni dans le paquet publié.
4. **Les jeux créés se partagent en patch** `.ups` à appliquer sur sa propre ROM, jamais en `.gba` complet.
5. **Ressources communautaires (FE-Repo)** :
   - jamais embarquées dans le dépôt : téléchargées à la demande par l'utilisateur ;
   - chaque ressource affiche sa **licence** : F2E (utilisation et modification libres) ou F2U (utilisation libre, modification interdite). **Une ressource non marquée est traitée comme F2U** ;
   - une ressource F2U ne peut pas être ouverte dans l'éditeur graphique (lecture seule) ;
   - les **crédits** de chaque ressource utilisée vont automatiquement dans le `CREDITS.txt` du projet.
6. **Nom et marque** : « FE Maker ». Ni logo ni charte graphique officiels de Nintendo. Le README précise que le projet n'est pas affilié à Nintendo / Intelligent Systems.
7. **Licence du code de FE Maker : GPL-3.0**, celle de FEBuilderGBA, dont on peut ainsi reprendre le code et les tables en toute légalité.
8. **Statut de chaque source réutilisée** (vérifié le 18/10/2026, à revérifier avant toute publication) :

   | Source | Licence constatée | Ce qu'on a le droit de faire |
   |---|---|---|
   | FEBuilderGBA | GPL-3.0 | Réutiliser du code et des données, FE Maker étant GPL-3.0, en créditant les auteurs |
   | Patchs communautaires intégrés à FEBuilderGBA | **Propres à chaque auteur** | Vérifier patch par patch ; à défaut, ne pas intégrer et renvoyer vers la source |
   | Décomp fireemblem8u | **Aucune licence** | Pas de licence à venir, le code étant au fond celui d'Intelligent Systems, mais FEU déclare par écrit ne revendiquer aucun droit et ne pas attaquer les projets dérivés ([#728](https://github.com/FireEmblemUniverse/fireemblem8u/issues/728), [#750](https://github.com/FireEmblemUniverse/fireemblem8u/issues/750)). FE Maker garde son modèle : décomp jamais redistribuée, modifications seulement dans l'overlay local. Le risque restant vient des ayants droit du jeu : à peser pour les phases 6 et 7 |
   | FE-Repo (graphismes) | F2E ou F2U selon la ressource, F2U par défaut | Voir point 5 |
   | FE-Repo-Music | À vérifier | Mêmes règles que FE-Repo tant que non vérifié |
   | Lex Talionis | À vérifier | Inspiration ergonomique uniquement |
   | ffta-decomp (charlie-troy) | **Aucune licence** | Inspiration uniquement |
   | gba-recomp (JRickey), FFTARecomp (Jorge262007) | MIT ou Apache-2.0 ; MIT | Réutilisables en respectant la licence et en citant l'auteur |
   | REA (morluto) | MIT | Outil de développement, pas une dépendance (section 7) |

9. **Citation** : toute source utilisée (code, données, documentation, ressource, recherche de la communauté, y compris les tables et formats de la ROM documentés par d'autres) est listée dans `CREDITS.md`, avec auteur, lien et licence, même pour un emprunt minime. En cas de doute sur une licence : demander à l'auteur et ne rien intégrer en attendant.

10. **IA générative** ([règle de FE Universe, 21/10/2026](https://feuniverse.us/t/ai-policy-updated-2026-10/38008)) : FE Maker est développé en très grande partie par IA et le dit partout (README, guide, annonce avec `[AI]` dans le titre, `CREDITS.txt` de chaque projet, car les jeux compilés contiennent son code). Aucun art ni aucune musique générés par IA, et aucune fonction qui en produirait à partir d'une phrase.

---

## 3. Architecture technique

```
Interface web locale (Svelte + TypeScript)
        │ API HTTP locale (JSON)
Serveur Python (FastAPI) : lit et écrit la décomp, projet, validation, FE-Repo, compilation
        │
Décomp FE8 (sous-module) + données du projet ──▶ Docker (agbcc) ──▶ .gba + patch .ups ──▶ mGBA
```

### Choix et justifications
- **Interface web locale** : même code partout, facile à faire évoluer. Empaquetage possible plus tard avec **Tauri**.
- **Svelte + TypeScript** : moins de code que React pour un même écran, lisible par des contributeurs débutants.
- **Python (FastAPI)** : écosystème riche pour manipuler fichiers, images et formats binaires.
- **Compilation via Docker** : la chaîne GBA est difficile à installer, surtout sous Windows ; la même image partout garantit des compilations reproductibles.
- **mGBA** : multiplateforme, open source, lancé par le bouton « Tester ».
- **Patchs `.ups`** : le format habituel de la communauté.
- **Corrections `BUGFIX` de la décomp** : option de compilation, désactivée par défaut tant que 3 blocs ne compilent pas (`docs/audit-decomp.md`).

### Le projet utilisateur
```
mon-jeu/
├── fe-maker.json        # nom, auteur, version, version du format, options
├── data/                # données éditées, en JSON lisible
├── assets/              # ressources ajoutées (portraits, animations, musique…)
├── backups/             # copies de data/ avant une conversion de format
├── CREDITS.txt          # généré automatiquement
└── build/               # sorties : .gba, patch .ups (ignoré par Git)
```
**Principe clé** : les données de l'utilisateur restent dans **notre format JSON**, **converties** vers le format de la décomp à la compilation. Le sous-module `decomp/` reste intact : ce qui change forme un overlay appliqué à une copie de travail, dans un volume Docker. Un projet non modifié redonne la ROM d'origine à l'octet près.

---

## 4. Phases du projet

Le détail daté de chaque point est dans `docs/journal.md`. Les vérifications en jeu sont des playtests sans fenêtre (`tests/local`) sauf mention contraire.

### Alpha publique (priorité actuelle, décidée le 30/10/2026)
Public : FE Universe, dépôt rendu public. Plateforme : Windows d'abord.

**État (02/11/2026)** :
1. **Préalables** : faits. Historique git sans ROM ni asset, position des mainteneurs connue (section 2).
2. **Fonctions avant le gel** : faites. Personnages, armes, classes et chapitres ajoutés sur les places libres, conditions et sauts, sprites de carte, démo de musique, patchs de confort.
3. **Gel** : hack témoin joué (« La Fuite de Lorn », fonctionnel dans l'ensemble) et test automatique au vert ; #129 reporté après l'alpha. **Reste** : décider le gel de la version `0.1.0-alpha`.
4. **Paquet sans Node** : prêt (`tools/make_release.py`, `release.yml` sur tag, pas encore lancé). La décomp se télécharge au premier lancement, au commit fixé.
5. **Image Docker sur ghcr.io** : prête. Elle est privée comme le dépôt : à rendre publique avec lui, sinon FE Maker la recompile.
6. **Premier lancement guidé** : prêt (`checks.py`).
7. **Retours des testeurs** : prêt (« Envoyer sur GitHub »). Un relais sans compte (ticket 75) a été écarté pour l'instant ; l'utilisateur imagine autre chose.
8. **Docs** : prêtes (guide FR/EN, limites connues, CHANGELOG). Passage d'une version à l'autre fait (`migrations.py`).
9. **À faire, décisions de l'utilisateur** : dépôt public, vérification des workflows, test sur une machine vierge, tag, annonce sur FEU (avec `[AI]` dans le titre).

### Phase 0 — Audit et fondations (terminée)
Décomp compilée et auditée (`docs/audit-decomp.md`), image Docker, modification vérifiée en jeu, tests en jeu sans fenêtre (`playtest.py`).

### Phase 1 — Personnages et objets (terminée, validée en jeu par l'utilisateur)
ROM vérifiée, création de projet, éditeurs d'objets et de personnages, compilation, patch `.ups`, bouton « Tester ». L'inventaire de départ est dans les unités du chapitre, comme dans le jeu.

### Phase 2 — Classes et système de combat
**État** :
- **Fait** : éditeur de classes (stats, déplacement, armes, promotions, capacités, animations, sprites, portrait générique), triangle des armes, efficacités, affinités, armes inutilisables signalées. Fiche personnage et fiche classe comparées à FEBuilder ; couleurs en combat par classe, tirées du portrait ou peintes sur le sprite (tickets 125 à 127).
- **Reste, fiche personnage** : ordre de tri, mini-portrait, animation propre au personnage, groupe de conversation, valeurs intermédiaires des rangs d'armes.
- **Reste, fiche classe** : vitesse de déplacement sur la carte, ordre de tri, coûts de déplacement terrain par terrain et par météo (voir « Après l'alpha »).
- **Fait, fiche objet (#144, 05/11)** : tout objet se copie (bâton, arme de monstre, potion, clé…) ; la copie agit comme son modèle partout où le moteur teste son numéro (`case`, `==`, tables de l'IA), vérifié en jeu pour un Vulnéraire copié (`tests/local`). « Effet comme » donne à une copie l'effet d'un autre objet du jeu (05/11) ; « PV rendus » (soins) et « Résistance en plus » (Eau bénite, 7 au plus) propres à la copie, vérifiés en jeu ; les boosters prennent leurs gains dans « Bonus de stats ». « Stat augmentée » : une copie d'Eau bénite peut donner un bonus qui baisse chaque tour à une autre stat (30 au plus, octets libres de l'unité), vérifié en jeu (05/11) ; ce bonus-là se perd en reprenant une sauvegarde de mi-chapitre (elle n'a pas de place pour lui).
- **Fiche objet** : comparée à FEBuilder le 01/11/2026. Effet de l'arme, points de rang, bonus de stats, propriétés, sort, texte d'utilisation, icône choisie dans une grille ; le type met à jour les attributs. Absents : effet d'usage (le moteur reconnaît consommables et bâtons à leur numéro, on n'ajoute donc que des armes), agrandissement de la table.
- **Armes magiques** : une case dans Propriétés et un sort, sur n'importe quelle arme. Une attaque à distance demande une animation qui lance le sort : la fiche objet prévient, la fiche de classe marque les mouvements vides (orange, rouge si une arme en a besoin), le filtre « Frappe à distance » de la bibliothèque donne 1 081 animations (275 haches, 407 lances ; liste à refaire avec `tools/scan_ranged_animations.py`). Essayé par l'utilisateur avec la hache du War Monk.
- **À faire** : stats moyennes d'une unité en montée automatique, dans son panneau de chapitre. Le calculateur de classe de FEBuilder est écarté : il double celui de la fiche personnage.
- **Limites** : couleurs du portrait approchées ; une animation importée ne protège pas sa monture ; camps ennemis et portraits importés non comparés à une référence.
- **Pas vérifié en jeu** : le portrait générique à l'écran (seule la valeur compilée l'est) ; le sort repris d'une autre arme (compilé). Double attaque, poison et bonus de stats sont joués en combat (playtest).

### Phase 3 — Chapitres
**État** :
- **Unités** : placement par glisser-déposer, inventaire, IA, unités de cinématique, renforts au tour N, niveau des alliés sur leur fiche, ennemis et génériques réglés dans le chapitre, montée automatique, niveaux selon la difficulté ; groupes rangés par tour (une ligne par tour, le tour choisi montré sur la carte, #153) ; groupes de scène (cinématiques) : un groupe que seules les scènes font venir, choisi dans une liste de la commande « Faire venir un groupe d'unités » (ou créé depuis elle), avec les scènes qui l'utilisent ; rangs d'armes de l'unité et portée des bâtons en vert (#157).
- **Fiche d'unité** : objet lâché à la mort, liens vers la réplique de combat et les dernières paroles, stats calculées (moyenne en montée automatique, comparée au jeu), carte affichée avec un changement, groupes dans l'ordre du jeu avec leurs sprites.
- **Objectifs** : s'emparer, vaincre tous les ennemis ou le chef, survivre, atteindre une zone, protéger, texte de l'écran de statut, brouillard de guerre. Tour de Valni et ruines de Lagdou en lecture seule.
- **Cartes** : peinture, blocs et bâtiments, terrains qui se raccordent tout seuls, « Remplir le vide », taille sur les quatre côtés (changements, villages, coffres, portes, unités et cases à prendre suivent ; pas les coordonnées écrites dans les scènes, un avertissement le dit), changements de carte, y compris sur les cartes qui n'en avaient pas, objets automatiques (villages, maisons, coffres, portes, murs fissurés, bois morts, magasins : leur changement et leur événement sont créés tout seuls), tuiles tournées, palettes et retouche de leurs couleurs (le brouillard suit), jeux de tuiles, aller-retour avec Tiled.
- **Règles** : convoi, préparation avant le combat, prise de case, brouillard, PV des murs ; météo, fond de combat (galerie) et caméra au départ, réunis en bas de la fiche (#143) et vérifiés en jeu. Icônes d'objectifs tirées du jeu (#140).
- **Reste** : décaler aussi les scènes quand une carte bouge à gauche ou en haut (`MOVE`, `CAMERA`, `CUMO_AT`, `AREA`, `SPAWN_*`, positions dans `SVAL`), import de cartes du FE-Repo et de jeux de tuiles (éditeur de style de FEBuilder), animations de tuiles, autres formats de carte (`.mar`, PNG), unités rangées par camp et par tour d'arrivée (ticket 6).
- **Reste, écarts avec FEBuilder (comparés le 01/11)** : chef de groupe, rangs de fin de chapitre, écran noir avant la première scène, musiques (phase 5). Reportés à sa demande : trajets d'arrivée point par point, pièges et balistes, placement et groupe propres au mode difficile.
- **Reste, retours du 03/11** : renforts répétés (le même groupe à chaque tour, ou tous les N tours, sur une plage de tours ; aujourd'hui un groupe arrive à un seul tour, « Dupliquer ce groupe » le recopie un tour plus tard) ; couleurs des cartes réglées comme celles des personnages, sur la palette partagée comme FEBuilder : faites le 05/11 (#147).
- **Pas vérifié en jeu** : murs fissurés, achats en magasin, recrutement, objectifs zone / protéger / survivre, niveaux selon la difficulté, une carte remplie, Tiled lui-même (pas installé).

### Phase 4 — Dialogues et événements
**État** :
- **Dialogues** : vue « Conversation » et vue « Étapes », mise en page avec la police du jeu, accents ; les 3404 messages du jeu passent l'aller-retour. Répliques, dernières paroles, conversations « Parler », recrutements, scènes de tour, soutiens.
- **Événements** : éditeur visuel en blocs (1234 scripts du jeu sans perte), scène simple d'ouverture et de fin, conditions et sauts, souvenirs et questions Oui / Non, déclencheurs en phrases (tour, plage de tours, « Parler », zone, souvenir). Commandes : chapitre suivant, caractéristique, objet, PV, IA, camp, retrait et retour dans l'équipe, changement de tuiles, météo, brouillard, teinte de l'écran, compteurs, bruitage, téléportation (ajoutées le 02/11, à valider par lui ; vérifiées en jeu sauf les scènes de zone et de souvenir, compilées).
- **Reste** : formulaires pour les appels de scripts, scène sur un village ou un drapeau quelconque, épilogue, objectifs scriptés (conditions combinées, cartes spéciales), textes en plusieurs langues, modèles de scènes (village et recrutement existent déjà par les objets de carte et « rejoint l'armée »).
- **Scènes de tour, de zone et de souvenir créées dans l'onglet Dialogues (#151, #152)** : bouton « Déroulé », toutes les commandes autour de leur dialogue, zone tracée à la souris sur la carte du chapitre (fait le 05/11).
- **Reste, écarts avec FEBuilder (comparés le 02/11 : 20 types de conditions, 624 commandes)** : reportés à sa demande, combat scripté, conditions de pièges (balistes, œufs, sols blessants), placement du joueur en difficile ; pour une autre version, carte du monde (escarmouches, ~50 commandes) et épilogues des personnages.
- **Pas vérifié en jeu** : le report d'un changement de caractéristique d'un chapitre à l'autre ou après une sauvegarde.

### Phase 5 — Bibliothèque de ressources communautaires
**État** :
- **Fait** : navigateur FE-Repo (dossiers, filtres, licences, crédits) et import depuis le PC pour les portraits, les animations de combat, les sprites de carte et les icônes d'objets (11 places, celles que le jeu n'utilise pas). Démo de musique : un MIDI pour la phase du joueur d'un chapitre, avec les instruments du jeu.
- **Limites** : 54 animations en plus de celles du jeu, environ 620 Ko.
- **Reste** : cartes, sorts, tilesets et décors dans le navigateur (absents de l'index de FE-Repo : parcourir ses dossiers par l'API GitHub ; les tilesets demandent l'import de jeux de tuiles). Icônes de compétences : attendent un système de compétences.
- **Musique (ticket 56 ; décidé le 02/11/2026 : on reste sur le MIDI)** : le moteur son est un séquenceur de notes et d'instruments, le streaming audio est trop lourd. À faire : l'équivalent des patchs FEBuilder « 16_tracks_12_sounds » (pistes et notes simultanées), « All instrument » / NIMAP (General MIDI complet, licence des échantillons à vérifier ; FE-Repo-Music en dépend) et « drumfix » ; import MIDI avec écoute ; musiques de FE-Repo **écoutables avant de les choisir**. Endroits à couvrir (relevés dans la décomp) : chapitre (`mapBgmIds` : phases joueur, ennemie, alliée, variantes après `EVFLAG_BGM_CHANGE`, ouverture ; victoire quand il reste peu d'ennemis, `victorySongEnemyThreshold`), scènes (MUSC, MUSS/MURE, fondus, volume), combat (attaque, défense, thème de chef `GetBanimBossBGM`, arme légendaire, promotion, arène), écrans fixes (titre, préparation, magasins, game over, épilogue, générique, salle des sons), jingles et bruitages.
- **Pas vérifié** : l'import d'animation depuis le PC en jeu ; la musique vérifiée en jeu, jamais écoutée.

### Après l'alpha
- **Présentation inspirée du wiki Fire Emblem** (fireemblemwiki.org, par exemple la page d'un chapitre : renforts tour par tour, tableaux d'unités) : l'utilisateur veut s'en inspirer pour d'autres écrans (ticket 153, 04/11/2026). Le chapitre tour par tour pourra aussi montrer les scènes de chaque tour.
- Rangs d'armes réglables par unité dans le chapitre (ticket 157) : à discuter avec l'utilisateur ; aujourd'hui ils sont affichés seulement.
- Agrandir les tables (objets, personnages, classes, cartes, chapitres).
- **À faire, décidé par l'utilisateur le 01/11/2026** : créer de nouveaux objets à usage et de nouveaux bâtons. Le moteur les reconnaît à leur numéro : il faudra rendre leur effet réglable.
- Ce que garde un projet (ticket 129) : retirer armes factices ou inutilisées, avec plusieurs filtres, et de même pour les classes, les personnages et les chapitres.
- Animations : modifier une animation (une épée ou une lance à un pirate), proposer les mouvements manquants depuis le FE-Repo ou les adapter d'une autre arme (ticket 134). L'animation de hache levée générée reste dans git (67140b2).
- Animation pour une seule arme, sans toucher aux autres armes du même type : presque finie, mise de côté en local (`git stash`), à reprendre avec l'accord de l'utilisateur.
- Projet vierge : retirer aussi les classes et les armes (gardées pour l'instant, le moteur en dépend).
- Créer un chapitre d'après une fiche du wiki Fire Emblem (ticket 67), pour recréer un chapitre d'un autre jeu.
- Coûts de déplacement selon la météo (demande du 02/11/2026) : le moteur a trois tables par type de déplacement (normal, pluie, neige et blizzard ; les autres météos prennent la normale), FE Maker ne fait que choisir le type. À faire : éditer ces tables terrain par terrain, puis éventuellement une table propre au sable (code de `GetUnitMovementCost`).
- Idées de l'utilisateur (02/11/2026), pour plus tard : un système de forge d'armes ; travailler à plusieurs sur un même projet.
- Idée de l'utilisateur (03/11/2026, #150) : des ennemis génériques tout prêts (classe, niveau, inventaire classique : soldat à la lance de fer, archer, mage…) à glisser-déposer sur la carte d'un chapitre.

### Phase 6 — Édition avancée et moteur
- Patchs de confort restants : `docs/patchs-qol.md`.
- Séparation force / magie (ticket 27) : `docs/separation-force-magie.md` ; piste retenue, reprendre le code C du C-SkillSys (MIT), à lancer avec l'accord de l'utilisateur.
- Mécaniques des hacks aimés par l'utilisateur (ticket 43, `docs/inspirations-hacks.md`) : objectif « s'échapper », chapitres annexes à condition, patchs à cocher (Locktouch, Pousser, échanges FE5), puis talents, arts de combat et reclassement.
- « Mode expert » : accès au code C depuis l'outil, modules moteur réutilisables et partagés entre utilisateurs.

### Chantier continu — Interface graphique
L'un des points les plus importants : tout doit être facile à prendre en main et très visuel. Maquettes : https://claude.ai/artifact/MKewiQUGuDhGbfbYt1UGsL.

Inspirations :
- **Super Mario Maker 2** : tester tout de suite, éléments glissés sur le niveau, annulation rassurante, leçons courtes au bon moment.
- **Wargroove** : pinceaux de terrain qui se raccordent, événements « condition → action », scènes sur une frise, campagne vue comme un enchaînement de cartes.
- **Advance Wars 1+2 Re-Boot Camp** : gros boutons de terrain, mode simple par défaut, effets du terrain affichés.
- **Autres** : déclencheurs en phrases de Warcraft III et StarCraft II, Battle for Wesnoth, Game Builder Garage, Levelhead, éditeurs de Heroes III et d'Age of Empires II ; RPG Maker MZ, aussi pour ce qu'il ne faut pas faire (listes de commandes lourdes).

Choix de l'utilisateur :
- **Campagne** : accueil en graphe des chapitres, avec des routes différentes possibles.
- **Carte** : mode simple par défaut, qui doit couvrir environ 80 % des besoins.
- **Conversations** : la scène sur une frise.
- **Déclencheurs** : phrases aux mots cliquables.
- **Thème** : fond clair chaud, barre du haut sombre, Nunito, gros boutons arrondis, bouton « Tester » vert.

**État** :
- **Fait** : page Campagne, test d'un chapitre donné, onglet Chapitres en trois vues, unités glissées, portée et zone de danger, pinceaux de terrain (bons sur rivières, montagnes et côtes, moyens sur les routes), historique des changements, explications en infobulles.
- **Reste** : créer un embranchement de routes depuis le graphe (à concevoir avec l'utilisateur), contenu exact des modes simple et avancé, écrans à ramener à leur maquette quand ils sont refaits, vérification avant export par un test automatique, petits tutoriels au bon moment.

### Phase 7 — Version PC (à redéfinir)
- **Recompilation statique de la ROM produite** avec [gba-recomp](https://github.com/JRickey/gba-recomp) ; [FFTARecomp](https://github.com/Jorge262007/FFTARecomp) montre le résultat visé. Avantage décisif : rien de la décomp n'est redistribué, seule la ROM du joueur est recompilée chez lui. À vérifier : gba-recomp s'appuie sur une carte des fonctions par jeu, qu'on pourrait générer depuis le fichier `.map` de la compilation.
- **Portage natif** du moteur, sur le modèle des portages PC de la communauté Pokémon, chargeant les assets depuis la ROM de l'utilisateur.
- **Export vers Lex Talionis**, si un format d'échange est réaliste.

---

## 5. Exigences transverses

- **Multiplateforme** : Windows d'abord, mais pas de script `.bat` ou `.sh` seul : prévoir les deux ou passer par Python.
- **Installation simple** : à terme, un installeur par plateforme. Prérequis tolérés au départ : Docker, mGBA.
- **Tests** : tests automatiques sans ROM sur des données fictives ; ceux qui ont besoin de la ROM sont lancés en local, jamais dans la CI publique.
- **CI GitHub** : lint et tests sans ROM.
- **Documentation** : guide utilisateur en français et en anglais ; guide contributeur.
- **Retours de test dans l'appli** : bouton « Ticket » toujours visible, avec captures et contexte joints ; stockage local, hors du dépôt.
- **Langues** : code et commentaires en anglais ; interface en français et en anglais. Espagnol et italien gelés jusqu'à une version plus aboutie ; chinois et japonais envisagés.

---

## 6. Règles pour le développement assisté par IA

- Repartir de ce document : la section du sujet traité, pas le fichier entier.
- Travailler **phase par phase**, ne pas anticiper les phases suivantes sans accord.
- **Ne jamais committer** : ROM, fichiers `.gba`, assets extraits de la ROM, ressources FE-Repo téléchargées.
- Avant de modifier la manière dont on lit une donnée de la décomp, consulter `docs/audit-decomp.md`.
- Chaque fonctionnalité terminée est vérifiée en jeu, ou notée « Pas vérifié en jeu » à la section 4.
- En cas de doute sur une licence de ressource : la traiter comme F2U.

---

## 7. Références

- Décomp FE8 : https://github.com/FireEmblemUniverse/fireemblem8u
- Portail des décomps Fire Emblem : https://laqieer.github.io/fe-decomp-portal/
- Ressources graphiques communautaires : https://github.com/Klokinator/FE-Repo
- Musique communautaire : https://github.com/Klokinator/FE-Repo-Music
- Explication F2E / F2U : https://feuniverse.us/t/regarding-graphics-assets/11550/5
- FEBuilderGBA (référence fonctionnelle, GPL-3.0) : https://github.com/FEBuilderGBA/FEBuilderGBA
- Fil FEBuilderGBA sur FE Universe : https://feuniverse.us/t/fe-builder-gba-if-you-have-any-questions-attach-report7z/2845
- Lex Talionis (moteur PC, référence ergonomique) : https://lt-maker.readthedocs.io/
- Communauté : https://feuniverse.us
- « Getting Started » de FEUniverse, index des tutoriels et de la documentation de FEBuilder : https://feuniverse.us/t/getting-started/10320

### Projets voisins à suivre

- [ffta-decomp](https://github.com/charlie-troy/ffta-decomp) (aucune licence, idées seulement) : réglages de l'IA en données éditables sans compilateur, validation par exécution des fonctions sur un processeur émulé, documentation précise de chaque table. Piste pour rendre éditable l'**IA des ennemis** de FE8.
- [gba-recomp](https://github.com/JRickey/gba-recomp) et [FFTARecomp](https://github.com/Jorge262007/FFTARecomp) : recompilation statique, piste principale de la phase 7.
- [Fork de FEBuilderGBA par laqieer](https://github.com/laqieer/FEBuilderGBA) (GPL-3.0, archivé) : version multiplateforme, ligne de commande, prise en charge de la décomp en aperçu, tests en jeu sans fenêtre.
- [REA](https://github.com/morluto/rea) (MIT) : rétro-ingénierie pilotée par des agents IA (Ghidra, IDA, Hopper), utile au **développement** pour les 6,7 % de données encore binaires. Prudence : popularité affichée inhabituelle, et son README met en garde contre les copies non officielles. À n'installer qu'après vérification, depuis sa source officielle.

---

## 8. Décisions en attente

- [ ] Gel de `0.1.0-alpha`, dépôt public, tag et annonce (section 4, Alpha publique)
- [ ] Embranchement de routes depuis la page Campagne : conception à faire avec l'utilisateur
- [ ] Remontée des tickets des testeurs : l'utilisateur imagine autre chose que le relais écarté
- [ ] Proposer aux mainteneurs de la décomp les corrections des 3 blocs `BUGFIX` cassés
- [ ] Piste retenue pour la version PC
- [ ] Passage entre FEBuilder et FE Maker (réflexion du 02/11/2026) : un projet FEBuilder est une ROM modifiée, un projet FE Maker est le code source de la décomp, et un `.ups` ne porte que des octets, pas le sens (personnages, cartes, événements). FEBuilder vers FE Maker : impossible aujourd'hui ; un import qui relit la ROM en suivant ses pointeurs serait faisable pour les tables, les textes, les portraits et les cartes, plus dur pour les événements (désassembleur d'Event Assembler ou de FEBuilder), impossible pour les patchs ASM. FE Maker vers FEBuilder : la ROM produite s'ouvre, mais en aller simple et sans garantie (le code recompilé change de place, FEBuilder lit les tables à des adresses fixes) ; pas testé. Deux `.ups` des deux outils ne se combinent pas. À dire dans l'annonce : FE Maker sert à un nouveau hack, pas à reprendre un hack FEBuilder. À décider : import partiel après l'alpha ? essai d'une ROM FE Maker dans FEBuilder ?
