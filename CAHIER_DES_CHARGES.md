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

**État (01/11/2026)** :
1. **Préalables** : faits. Historique git sans ROM ni asset, position des mainteneurs connue (section 2).
2. **Fonctions avant le gel** : faites. Personnages, armes, classes et chapitres ajoutés sur les places libres, conditions et sauts, sprites de carte, démo de musique, patchs de confort.
3. **Gel** : hack témoin joué (« La Fuite de Lorn », fonctionnel dans l'ensemble) et test automatique au vert, aucun ticket ouvert. **Reste** : décider le gel de la version `0.1.0-alpha`.
4. **Paquet sans Node** : prêt (`tools/make_release.py`, `release.yml` sur tag, pas encore lancé). La décomp se télécharge au premier lancement, au commit fixé.
5. **Image Docker sur ghcr.io** : prête. Elle est privée comme le dépôt : à rendre publique avec lui, sinon FE Maker la recompile.
6. **Premier lancement guidé** : prêt (`checks.py`).
7. **Retours des testeurs** : prêt (« Envoyer sur GitHub »). Un relais sans compte (ticket 75) a été écarté pour l'instant ; l'utilisateur imagine autre chose.
8. **Docs** : prêtes (guide FR/EN, limites connues, CHANGELOG). Passage d'une version à l'autre fait (`migrations.py`).
9. **À faire, décisions de l'utilisateur** : dépôt public, vérification des workflows, test sur une machine vierge, tag, annonce sur FEU.

### Phase 0 — Audit et fondations (terminée)
Décomp compilée et auditée (`docs/audit-decomp.md`), image Docker, modification vérifiée en jeu, tests en jeu sans fenêtre (`playtest.py`).

### Phase 1 — Personnages et objets (terminée, validée en jeu par l'utilisateur)
ROM vérifiée, création de projet, éditeurs d'objets et de personnages, compilation, patch `.ups`, bouton « Tester ». L'inventaire de départ est dans les unités du chapitre, comme dans le jeu.

### Phase 2 — Classes et système de combat
**État** :
- **Fait** : éditeur de classes (stats, déplacement, armes, promotions, capacités, animations, sprites, portrait générique), triangle des armes, efficacités, affinités, armes inutilisables signalées. Fiche personnage et fiche classe comparées à FEBuilder ; couleurs en combat par classe, tirées du portrait ou peintes sur le sprite (tickets 125 à 127).
- **Reste, fiche personnage** : ordre de tri, mini-portrait, animation propre au personnage, groupe de conversation, valeurs intermédiaires des rangs d'armes.
- **Reste, fiche classe** : vitesse de déplacement sur la carte, ordre de tri, tables de pluie, de neige et de terrain réglables une à une.
- **Reste, fiche objet** (comparée le 01/11/2026) : effet de l'arme (poison, vol de PV, Dévil, moitié des PV, pétrification), bonus de stats, points de rang gagnés par coup, propriétés (attaque la résistance, dégâts magiques, incassable, invendable, double attaque, sans riposte, triangle inversé, ignore la défense, annule les efficacités contre les volants, annule les critiques, pas de Marteau), texte d'utilisation, sort lié à une arme. Changer le type d'un objet ne met pas à jour ses attributs (arme, bâton, magie) : à corriger. Ajouter un objet : armes seulement, le moteur reconnaît consommables et bâtons à leur numéro.
- **À faire** : stats moyennes d'une unité en montée automatique, dans son panneau de chapitre. Le calculateur de classe de FEBuilder est écarté : il double celui de la fiche personnage.
- **Limites** : couleurs du portrait approchées ; une animation importée ne protège pas sa monture ; camps ennemis et portraits importés non comparés à une référence.
- **Pas vérifié en jeu** : le portrait générique à l'écran (seule la valeur compilée l'est).

### Phase 3 — Chapitres
**État** :
- **Unités** : placement par glisser-déposer, inventaire, IA, unités de cinématique, renforts au tour N, niveau des alliés sur leur fiche, ennemis et génériques réglés dans le chapitre, montée automatique, niveaux selon la difficulté.
- **Objectifs** : s'emparer, vaincre tous les ennemis ou le chef, survivre, atteindre une zone, protéger, texte de l'écran de statut, brouillard de guerre. Tour de Valni et ruines de Lagdou en lecture seule.
- **Cartes** : peinture, blocs et bâtiments, terrains qui se raccordent tout seuls, « Remplir le vide », taille, changements de carte, objets automatiques (villages, maisons, coffres, portes, murs fissurés, bois morts, magasins : leur changement et leur événement sont créés tout seuls), tuiles tournées, palettes, jeux de tuiles, aller-retour avec Tiled.
- **Règles** : convoi, préparation avant le combat et prise de case réglables.
- **Reste** : import de cartes du FE-Repo, couche de changements pour une carte qui n'en a pas, unités rangées par camp et par tour d'arrivée (ticket 6).
- **Pas vérifié en jeu** : murs fissurés, achats en magasin, recrutement, objectifs zone / protéger / survivre, niveaux selon la difficulté, une carte remplie, Tiled lui-même (pas installé).

### Phase 4 — Dialogues et événements
**État** :
- **Dialogues** : vue « Conversation » et vue « Étapes », mise en page avec la police du jeu, accents ; les 3404 messages du jeu passent l'aller-retour. Répliques, dernières paroles, conversations « Parler », recrutements, scènes de tour, soutiens.
- **Événements** : éditeur visuel en blocs (1234 scripts du jeu sans perte), scène simple d'ouverture et de fin, conditions et sauts, « Passer à un autre chapitre », « Changer une caractéristique », souvenirs et questions Oui / Non. Déclencheurs de tour et de « Parler » en phrases cliquables.
- **Reste** : formulaires pour les appels de scripts, ajout d'une scène à n'importe quel déclencheur (villages, zones et drapeaux en lecture), épilogue, objectifs scriptés (conditions combinées, cartes spéciales), gestion multilingue des textes.
- **Pas vérifié en jeu** : le report d'un changement de caractéristique d'un chapitre à l'autre ou après une sauvegarde.

### Phase 5 — Bibliothèque de ressources communautaires
**État** :
- **Fait** : navigateur FE-Repo (dossiers, filtres, licences, crédits) et import depuis le PC pour les portraits, les animations de combat et les sprites de carte. Démo de musique : un MIDI pour la phase du joueur d'un chapitre, avec les instruments du jeu.
- **Limites** : 54 animations en plus de celles du jeu, environ 620 Ko.
- **Reste** : icônes, cartes, tilesets et décors dans le navigateur. Musique (ticket 56, en pause) : les autres phases, le réglage des instruments, FE-Repo-Music (il faut le jeu d'instruments NIMAP2).
- **Pas vérifié** : l'import d'animation depuis le PC en jeu ; la musique vérifiée en jeu, jamais écoutée.

### Après l'alpha
- Agrandir les tables (objets, personnages, classes, cartes, chapitres).
- Projet vierge : retirer aussi les classes et les armes (gardées pour l'instant, le moteur en dépend).
- Créer un chapitre d'après une fiche du wiki Fire Emblem (ticket 67), pour recréer un chapitre d'un autre jeu.

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
