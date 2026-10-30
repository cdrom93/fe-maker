# FE Maker — Cahier des charges

> Document de référence du projet. À placer à la racine du dépôt.
> Toute session de développement (humaine ou assistée par IA) repart de ce document.
> Si une décision change, on met ce fichier à jour **avant** de coder.

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
| Windows uniquement | **Windows, Linux, macOS** |
| Ressources graphiques à chercher soi-même sur les forums | **Bibliothèque communautaire intégrée** (FE-Repo), avec licences et crédits gérés automatiquement |
| Vocabulaire technique | Vocabulaire de joueur, aide contextuelle, valeurs par défaut sensées, aperçus visuels partout |

### Principes d'ergonomie (non négociables)
1. **Jamais d'adresse mémoire, de pointeur ou d'hexadécimal visibles** dans le mode normal. Un « mode expert » peut les montrer.
2. **Un aperçu visuel pour tout** : portrait, sprite, carte, fiche de stats telle qu'elle apparaîtra en jeu.
3. **Assistants pas à pas** pour les tâches courantes (nouveau personnage, nouveau chapitre, nouvelle classe).
4. **Annuler / rétablir** partout. Sauvegarde automatique.
5. **Validation en direct** : l'outil empêche ou signale ce qui casserait le jeu (stat hors limite, ID en double, carte sans point de départ…) avant la compilation.
6. **Un seul bouton « Tester »** : compile et lance le jeu dans l'émulateur.
7. Interface **en français et en anglais** dès le départ (fichiers de traduction).
8. **Tout ce qui est mentionné est cliquable** : une arme, une classe, un personnage, une liste… cité n'importe où (rappel, puce, liste déroulante, message d'erreur) ouvre directement sa fiche pour l'éditer, sans aller-retour entre les onglets. Cette règle vaut pour tous les éditeurs à venir (chapitres, cartes, dialogues…).
9. **Illustrer avec les visuels du jeu** (ajouté le 30/10/2026, ticket 54) : icônes d'armes et d'objets, portraits, sprites de carte, tuiles, avant tout emoji ou icône dessinée. Pas d'emoji décoratif devant le texte d'un bouton, d'un lien, d'un titre ou d'une phrase ; un emoji seulement s'il sert d'icône (outils de la carte, types d'objectif, repères ⚠ ⭐ ✎).

---

## 2. Cadre légal et licences (à respecter strictement)

Le projet doit pouvoir vivre publiquement sur GitHub sans risque. Règles :

1. **Aucune donnée Nintendo dans le dépôt.** Pas de ROM, pas d'assets extraits, pas de fichiers générés à partir de la ROM.
2. **L'utilisateur fournit sa propre ROM** (FE8 US, vérifiée par SHA1 `c25b145e37456171ada4b0d440bf88a19f4d509f`) au premier lancement. L'outil refuse toute autre ROM avec un message clair.
3. **La décomp FE8 est un sous-module Git**, jamais copiée dans notre dépôt.
4. **Partage des jeux créés sous forme de patch** (.ups) à appliquer sur sa propre ROM, jamais de .gba complet distribué par l'outil.
5. **Ressources communautaires (FE-Repo)** :
   - jamais embarquées dans le dépôt : téléchargées à la demande par l'utilisateur ;
   - chaque ressource affiche sa **licence** : F2E (libre d'utilisation et de modification) ou F2U (libre d'utilisation, modification interdite). **Par défaut, une ressource non marquée est traitée comme F2U** ;
   - une ressource F2U ne peut pas être ouverte dans l'éditeur graphique (lecture seule) ;
   - les **crédits** de chaque ressource utilisée sont ajoutés automatiquement à un fichier `CREDITS.txt` du projet et peuvent être intégrés à l'écran de crédits du jeu.
6. **Nom et marque** : « FE Maker » est le nom retenu. Ne pas utiliser les logos ni la charte graphique officiels de Nintendo dans l'interface ou la communication. Mentionner dans le README que le projet n'est pas affilié à Nintendo / Intelligent Systems.
7. **Licence du code de FE Maker : GPL-3.0.** Raison : FEBuilderGBA est sous GPL-3.0. Reprendre ou porter son code (ou ses tables de données) oblige à publier FE Maker sous GPL-3.0 ; choisir cette licence dès le départ permet de s'appuyer sur son travail en toute légalité et s'inscrit dans l'esprit de la communauté.
8. **Statut de chaque source réutilisée** (vérifié le 18/10/2026, à revérifier avant toute publication) :

   | Source | Licence constatée | Ce qu'on a le droit de faire |
   |---|---|---|
   | FEBuilderGBA | GPL-3.0 (déclarée dans le README) | Réutiliser / porter du code et des données à condition que FE Maker soit GPL-3.0 et que les auteurs soient crédités |
   | Patchs communautaires intégrés à FEBuilderGBA | **Propres à chaque auteur** (ne sont pas forcément couverts par la GPL de FEBuilderGBA) | Vérifier patch par patch auteur + conditions ; à défaut, ne pas intégrer et renvoyer vers la source |
   | Décomp fireemblem8u | **Aucun fichier LICENSE trouvé** à la racine du dépôt | Par défaut, sans licence = tous droits réservés. On l'utilise **uniquement comme sous-module non modifié**. Toute redistribution de code modifié de la décomp (modules moteur, phase 6, version PC) est **bloquée tant que les mainteneurs n'ont pas donné leur accord écrit**. Réponse déjà donnée (issues [#728](https://github.com/FireEmblemUniverse/fireemblem8u/issues/728), 09/01/2026, et [#750](https://github.com/FireEmblemUniverse/fireemblem8u/issues/750), 24/09/2026) : pas de licence à venir (le code est au fond celui d'Intelligent Systems), mais déclaration écrite que FEU ne se considère titulaire d'aucun droit sur ce code et n'attaquera pas les projets dérivés. FE Maker garde son modèle : décomp jamais redistribuée, modifications seulement dans l'overlay local |
   | FE-Repo (graphismes) | F2E ou F2U selon la ressource, F2U par défaut | Voir point 5 |
   | FE-Repo-Music | À vérifier | Même règles que FE-Repo tant que non vérifié |
   | Lex Talionis | À vérifier | Inspiration ergonomique uniquement, aucune reprise de code sans vérification |
   | ffta-decomp (charlie-troy) | **Aucune licence** (vérifié le 20/10/2026) | Inspiration uniquement (méthodes, organisation de la doc), aucune reprise de code ni de données |
   | gba-recomp (JRickey) | MIT ou Apache-2.0 ; base de fonctions gamedb.sqlite en CC0 | Réutilisable en respectant la licence et en citant l'auteur |
   | FFTARecomp (Jorge262007) | MIT (basé sur gba-recomp) | Réutilisable en respectant la licence et en citant l'auteur |
   | REA (morluto) | MIT | Outil de développement, pas une dépendance de FE Maker (voir section 7) |

9. **Règle générale de citation** : toute source utilisée (code, données, documentation, ressource, recherche de la communauté) est listée dans `CREDITS.md` à la racine du dépôt FE Maker, avec auteur, lien et licence. Aucune exception, même pour un emprunt minime. En cas de doute sur une licence : **demander à l'auteur avant d'utiliser**, et ne rien intégrer en attendant.
10. **Données d'analyse de la ROM** (tables, offsets, formats documentés par la communauté) : même s'il s'agit de faits techniques, on cite systématiquement qui les a documentés, comme le fait FEBuilderGBA lui-même.

---

## 3. Architecture technique

```
┌──────────────────────────────────────────────┐
│  Interface (appli web locale, navigateur)    │  ← plus tard empaquetée avec Tauri
│  - éditeurs, aperçus, assistants             │
└───────────────────┬──────────────────────────┘
                    │ API HTTP locale (JSON)
┌───────────────────▼──────────────────────────┐
│  Serveur Python (FastAPI)                    │
│  - lit / écrit les données de la décomp      │
│  - modèle de projet FE Maker                 │
│  - validation                                │
│  - gestion des ressources FE-Repo            │
│  - pilote la compilation                     │
└───────┬───────────────────────────┬──────────┘
        │                           │
┌───────▼─────────┐       ┌─────────▼──────────┐
│ Décomp FE8      │       │ Docker             │
│ (sous-module)   │       │ chaîne GBA         │
│ + données du    │       │ (agbcc, devkitARM) │
│ projet          │──────▶│ → fichier .gba     │
└─────────────────┘       └─────────┬──────────┘
                                    │
                          ┌─────────▼──────────┐
                          │ Émulateur (mGBA)   │
                          │ ou console         │
                          └────────────────────┘
```

### Choix et justifications
- **Interface web locale** : même code sur Windows, Linux, macOS ; facile à faire évoluer ; accessible aux contributeurs. Empaquetage en application de bureau avec **Tauri** dans une phase ultérieure.
- **Front-end : Svelte + TypeScript** (décidé en fin de phase 0). Critère principal : simplicité. Moins de code que React pour un même écran, lisible par des contributeurs débutants, s'empaquette bien avec Tauri.
- **Serveur Python (FastAPI)** : écosystème riche pour manipuler fichiers, images (Pillow) et formats binaires.
- **Compilation via Docker** : la chaîne GBA est difficile à installer, surtout sous Windows. Une image Docker identique partout garantit des compilations reproductibles. Le README de la décomp mentionne une branche (`remove_tools` de laqieer) qui utilise déjà Docker : à étudier comme base.
- **Émulateur** : mGBA (multiplateforme, open source), lancé automatiquement par le bouton « Tester ».

### Le projet utilisateur
Un projet FE Maker est un dossier contenant :
```
mon-jeu/
├── fe-maker.json        # métadonnées : nom, auteur, version, version de la décomp utilisée
├── data/                # données éditées (personnages, classes, objets, chapitres…) en JSON lisible
├── assets/              # ressources ajoutées (portraits, sprites…) + leur licence
├── CREDITS.txt          # généré automatiquement
└── build/               # sorties : .gba, patch .ups (ignoré par Git)
```
**Principe clé** : les données de l'utilisateur sont stockées dans **notre propre format JSON lisible**, puis **converties** vers le format attendu par la décomp au moment de la compilation. On ne modifie jamais directement les fichiers de la décomp à la main. Avantages : mise à jour de la décomp possible, projets partageables, fichiers versionnables avec Git.

**Copie de travail** : le sous-module `decomp/` reste toujours intact (voir section 2, point 8). À chaque compilation, FE Maker copie la décomp dans `mon-jeu/build/decomp/`, y écrit les données converties du projet, puis compile cette copie. Le sous-module sert uniquement de modèle de départ.

### Structure du dépôt FE Maker
```
fe-maker/
├── CAHIER_DES_CHARGES.md
├── README.md
├── decomp/              # sous-module : FireEmblemUniverse/fireemblem8u
├── server/              # Python / FastAPI
├── ui/                  # interface web
├── docker/              # image de compilation
├── docs/                # documentation utilisateur et contributeur
└── tests/
```

---

## 4. Phases du projet

### Phase 0 — Audit et fondations ✅ (terminée le 18/10/2026, voir `docs/audit-decomp.md`)
**Objectif : comprendre la décomp avant de construire dessus.**
- Cloner la décomp, la compiler avec une ROM d'origine (résultat attendu : `fireemblem8.gba: OK`).
- **Audit des données** : pour chaque type de donnée (personnages, classes, objets, chapitres, cartes, événements, textes, graphismes), identifier :
  - où elle se trouve (C, JSON, assembleur, binaire) ;
  - si elle est lisible et modifiable proprement ;
  - comment la décomp la compile.
  - **Attention** : la décomp n'est peut-être pas complète (présence d'un dossier `asm/`). Certaines données peuvent encore être en assembleur ou en binaire brut. Documenter ces zones.
- Produire `docs/audit-decomp.md` avec les résultats.
- Créer l'image Docker de compilation et vérifier qu'elle fonctionne sous Windows (Docker Desktop / WSL2).
- Vérifier qu'une **modification triviale** (changer une stat de base dans la décomp) compile et apparaît en jeu.
- Tests en jeu automatiques sans fenêtre (`server/fe_maker/playtest.py`, image `docker/playtest`, 24/10/2026) : servent à vérifier en jeu chaque fonction.
- Vérifié en jeu par ces tests : convoi, objets de carte (village, coffre, porte, maison, armurerie, bois mort), jeux de tuiles, palettes, tuiles tournées, portraits, accents, dialogues de tour, répliques, soutiens, classes, renforts, armes, objectifs « s'emparer ». Pas couverts : murs fissurés, achats en magasin, recrutement, objectifs zone / protéger / survivre.

### Phase 1 — POC : personnages et objets ✅ (validée en jeu le 18/10/2026)
**Objectif : valider toute la chaîne de bout en bout sur les données les plus simples.**
- Premier lancement : sélection de la ROM, vérification SHA1.
- Création d'un projet FE Maker.
- **Éditeur d'objets** : nom, type d'arme, puissance, précision, critique, poids, portée, durabilité, prix, icône.
- **Éditeur de personnages** : nom, classe, niveau de départ, stats de base, taux de croissance, rangs d'armes, portrait (aperçu). L'**inventaire de départ** est déplacé en phase 3 : dans le jeu, il est défini par chapitre, dans le placement des unités, et non dans la fiche du personnage (voir `docs/audit-decomp.md`).
- Conversion projet → décomp, compilation Docker, génération du .gba et du patch .ups.
- Bouton « Tester » qui lance mGBA.
- **Critère de réussite** : je modifie un personnage dans l'interface, je clique sur « Tester », je vois la modification en jeu.

### Phase 2 — Classes et système de combat 🚧 (implémentée le 18/10/2026, test en jeu à faire)
- Éditeur de classes : stats de base et maximales, mouvement, type de déplacement, armes utilisables, promotions, compétences.
- Triangle des armes, efficacités (armes anti-cavalerie, anti-volants…).
- Aperçu de la fiche personnage complète (perso + classe).
- Ajouté en cours de route : capacités (dont verrous d'armes) et affinité des personnages ; options de test (démarrage direct sur la carte).
- Avertissement des armes que les unités ne pourront pas utiliser (24/10/2026).

### Phase 3 — Chapitres 🚧 (en cours)
**État (30/10/2026)** — le détail daté est dans `docs/journal.md`.
- **Unités** : placement par glisser-déposer, ajout, duplication et suppression, personnage, classe (unités génériques), niveau, inventaire, IA ; unités de cinématique séparées ; renforts au tour N, « Dupliquer ce groupe ».
- **Objectifs** : s'emparer d'une case, vaincre tous les ennemis ou le chef, survivre N tours (ou vaincre le chef), atteindre une zone, personnage à protéger ; texte de l'écran de statut. Lecture seule : tour de Valni et ruines de Lagdou. Brouillard de guerre par chapitre.
- **Cartes** : peinture (crayon, rectangle, remplissage, pipette, blocs, bâtiments entiers), terrains et leurs effets, taille, changements de carte (zone tracée à la souris), objets automatiques (villages et leurs ruines, maisons, coffres, portes, murs fissurés, bois morts, magasins), tuiles tournées et retournées, terrain d'une tuile, palettes, jeux de tuiles, aller-retour avec Tiled.
- **Règles** : convoi par personnage et par chapitre, qui peut s'emparer des cases.
- **Pas encore testé en jeu** : murs fissurés, achats, Tiled lui-même (pas installé).
- **Reste** : import de cartes du FE-Repo (phase 5), couche de changements pour une carte qui n'en a pas.
- Liste et ordre des chapitres, objectifs (déroute, boss, survie, s'emparer…).
- **Placement des unités** sur les cartes existantes : alliés, ennemis, renforts, IA des ennemis, par glisser-déposer sur un aperçu de la carte.
- **Éditeur de cartes** : peinture de tuiles à partir des tilesets, terrains, import de cartes depuis FE-Repo.
- **Changements de carte automatiques** (demande de l'utilisateur, 23/10/2026, priorité) : régler les couches de changements à la main est trop pénible. On dessine la carte, on pose un coffre, un village à visiter, une porte, un mur fissuré… et FE Maker crée tout seul le changement (état « après » : coffre ouvert, village fermé, porte ouverte, décombres), sa position, son numéro et ce qu'il faut pour qu'il fonctionne (événements de village, contenu du coffre), au moins pour les cas classiques. But : dessiner la carte simplement et qu'elle fonctionne quasiment toute seule. Le réglage manuel des changements reste disponible pour les cas particuliers.

### Phase 4 — Dialogues et événements 🚧 (commencée le 23/10/2026)
**État (30/10/2026)** — le détail daté est dans `docs/journal.md`.
- **Dialogues** : vue « Conversation » (bulles, portraits glissés sur la scène, expressions comme états) et vue « Étapes » ; mise en page automatique avec la police du jeu, lettres accentuées ; les 3404 messages du jeu passent l'aller-retour.
- **Répliques et conversations** : répliques de combat et dernières paroles, conversations « Parler » et recrutements, scènes au début d'un tour, soutiens (83 paires du jeu, ajout et retrait).
- **Événements** : éditeur visuel en blocs (1234 scripts du jeu sans perte), « scène simple » d'ouverture et de fin, nouveaux dialogues dans les scripts.
- **Vérifié en jeu** (playtest) : accents et coupure des bulles, dialogue de tour, répliques, soutien, prologue → chapitre 1 avec une scène simple.
- **Reste** : formulaires pour les commandes avancées (conditions, sauts, appels), ajout d'une scène à n'importe quel déclencheur, conversations sur une frise (choix B).

- Éditeur de dialogues avec aperçu (portraits, position, émotions).
- Éditeur d'événements **visuel** (blocs ou formulaires, pas de code) : début/fin de chapitre, recrutements, villages, conversations, conditions de victoire.
- **Objectifs scriptés** (demande de l'utilisateur, 23/10/2026) : rendre modifiables les objectifs que la phase 3 affiche en lecture seule — escorte (protéger un personnage), zones à atteindre, « survivre N tours ou vaincre le chef », conditions combinées, cartes spéciales — et pouvoir en créer de nouveaux de ce type.
- Soutiens entre personnages.
- Textes : gestion multilingue.

### Phase 5 — Bibliothèque de ressources communautaires
**État (30/10/2026)** — le détail daté est dans `docs/journal.md`.
- **Portraits** : remplacer un portrait du jeu ou en ajouter (n° 173 et suivants) ; planche 128 × 112, bouche et yeux trouvés tout seuls ; navigateur FE-Repo (dossiers, filtre F2E, crédits écrits dans le CREDITS.txt du projet).
- **Animations de combat** (ticket 44) : la fiche de classe joue les 201 animations du jeu ; bibliothèque FE-Repo (aperçu, armes, auteurs) ; filtre par armes, plusieurs à cocher (tickets 47 et 48) ; import d'une animation pour une arme d'une classe, vérifié en jeu, couleurs des autres camps, boucles des sorts (« L » de FEditor, ticket 46) ; les trois haches de lancer et les trois livres (anima, lumière, ténèbres) sont liés : réglés d'un coup, l'un d'eux peut garder la sienne, celui qui n'en a pas prend celle du groupe (tickets 49 et 51) ; un mage qui frappe à l'épée joue enfin l'animation d'épée (ticket 52, vérifié en jeu) ; import depuis le PC : dossier d'une arme (script FEditor et images) ou son .zip (ticket 53, vérifié par l'API et dans l'interface, pas en jeu). Limites : 54 animations en plus de celles du jeu, environ 620 Ko.
- **Reste** : nouvelles classes complètes (ticket 44, étape 4, avec l'accord de l'utilisateur), sprites de carte, icônes et cartes dans le même navigateur.
- Navigateur intégré de FE-Repo (portraits, animations de combat, sprites de carte, icônes, cartes, tilesets, décors) avec aperçus.
- Exploiter `file_urls.json` du dépôt FE-Repo comme index si le format s'y prête.
- Téléchargement à la demande, conversion automatique au format GBA (palette, taille), gestion des licences F2E/F2U et des crédits (voir section 2).
- Import de ressources personnelles (PNG) avec conversion et vérification de palette.
- Musique (FE-Repo-Music) : à étudier, format plus complexe.

### Phase 6 — Édition avancée et moteur
- Étudié le 24/10/2026 (ticket 32) : liste des patchs de confort de FEBuilder à proposer, par priorité, avec la façon de les faire sur la décomp (`docs/patchs-qol.md`). Ticket 27 : séparation force / magie, plan dans `docs/separation-force-magie.md` (environ 80 endroits du moteur, format de sauvegarde à agrandir ; C-SkillSys ne se branche pas sur la décomp). Piste retenue : reprendre le code C du C-SkillSys (MIT) directement dans la décomp ; à lancer avec l'accord de l'utilisateur.
- Mécaniques des hacks aimés par l'utilisateur (ticket 43, `docs/inspirations-hacks.md`) : brouillard de guerre fait ; à suivre : objectif « s'échapper », chapitres annexes à condition (avec les routes de la page Campagne), patchs à cocher (Locktouch, Pousser, échanges FE5), puis talents, arts de combat et reclassement avec la séparation force / magie. Plus tard : étude détaillée de chacun de ces hacks (liste et liens dans `docs/inspirations-hacks.md`).
- « Mode expert » : accès au code C de la décomp depuis l'outil, système de modules/patchs moteur réutilisables (ex. compétences, nouvelles mécaniques).
- Partage de modules entre utilisateurs.

### Chantier continu — Interface graphique (ajouté le 25/10/2026)
L'interface est l'un des points les plus importants : tout doit être facile à prendre en main et très visuel. Inspirations retenues (jeux avec éditeur) :
- **Super Mario Maker 2** : tester tout de suite depuis l'endroit où l'on est ; palette d'éléments glissés sur le niveau, variantes d'un geste, éléments récents ; retours immédiats (son, animation) ; annulation rassurante avec historique ; niveau vérifié jouable avant publication ; leçons courtes au moment où l'on découvre un outil (dojo de Yamamura).
- **Wargroove 1 et 2** : pinceaux de terrain qui se raccordent tout seuls (routes, rivières, côtes) ; événements « condition → action » avec drapeaux de campagne ; éditeur de scènes sur une frise (fond, météo, musique, acteurs) ; campagne vue comme un enchaînement de cartes.
- **Advance Wars 1+2 : Re-Boot Camp** (Design Room) : une grille, quelques gros boutons de terrain, unités placées d'avance ; mode simple par défaut, détails rangés dans un mode avancé ; effets du terrain affichés pendant qu'on peint.
- **Autres** : éditeur de déclencheurs de Warcraft III / StarCraft II (actions écrites en phrases aux mots cliquables) ; Battle for Wesnoth (éditeur libre, transitions de terrain automatiques, camps réglés en quelques boutons) ; Game Builder Garage (briques de programmation expliquées) ; Levelhead (tester et éditer sans coupure) ; RPG Maker MZ (pages d'événement, et ce qu'il ne faut pas faire : listes de commandes lourdes) ; éditeurs de scénarios de Heroes III et Age of Empires II (objectifs et événements datés dans une même fiche).

Priorités proposées :
1. Tester un chapitre donné : bouton ▶ sur chaque chapitre, avec ses unités, sans repasser par le prologue.
2. Unités et objets glissés sur la carte, zones de mouvement et de danger visibles pendant l'édition.
3. Pinceaux de terrain qui se raccordent tout seuls (raccords appris des cartes du jeu).
4. Événements en phrases cliquables ; scènes sur une frise avec les acteurs.
5. Vérification avant export par un test automatique ; petits tutoriels au bon moment.

Maquettes cliquables (25/10/2026) : https://claude.ai/artifact/MKewiQUGuDhGbfbYt1UGsL.

Choix de l'utilisateur (25/10/2026) :
- **Campagne** : l'accueil en graphe des chapitres est retenu, avec des routes différentes possibles (embranchements).
- **Carte** : mode simple par défaut ; le contenu exact du mode simple et du mode avancé sera réglé plus tard. Objectif : que le mode simple couvre environ 80 % des besoins, en automatisant le plus possible les éléments de carte (villages, coffres, portes, murs, bois morts, magasins : déjà automatiques quand ils sont peints).
- **Conversations** : la scène sur une frise (direction B).
- **Thème** (fait le 25/10/2026) : l'appli entière prend l'apparence des maquettes : fond clair chaud, barre du haut sombre, police Nunito (OFL, fournie avec l'appli), gros boutons arrondis, onglets en pastilles, bouton « Tester » vert. La disposition des écrans ne change pas encore : chaque écran rejoindra sa maquette quand il sera refait.
- **Fait** : page Campagne (graphe des chapitres de gauche à droite, fiche du chapitre, option « Carte du monde entre les chapitres », objectif et unités sur les cartes, liste « À faire pour ce projet », « ▶ Tester ce chapitre ») ; effets du terrain dans l'éditeur de carte.
- **Reste, dans l'ordre** : embranchements de routes dans le graphe ; carte : portée et zone de danger, historique visible des annulations ; onglet Chapitres refait (ticket 6) : unités aux couleurs de leur camp (bleu alliés, rouge ennemis, vert autres), présentées dans l'ordre placement des alliés, ennemis de départ, unités vertes, puis les renforts rangés par tour d'arrivée ; le but est d'y voir clair et de rendre la création d'un chapitre simple.
- **Déclencheurs** : les phrases (direction A) suivent la structure du jeu (listes d'événements du chapitre : tours, conversations, cases, zones et drapeaux, puis un script) ; à confirmer.

### Phase 7 — Version PC (à redéfinir)
Trois pistes à évaluer le moment venu :
- **Recompilation statique de la ROM produite** avec [gba-recomp](https://github.com/JRickey/gba-recomp) (MIT/Apache-2.0) : l'outil traduit à l'avance une ROM GBA en programme natif (Windows, Linux, macOS), avec un modèle matériel complet (affichage, son, sauvegardes, manettes). [FFTARecomp](https://github.com/Jorge262007/FFTARecomp) montre le résultat visé pour un jeu tactique : installeur « choisissez votre ROM, cliquez », écran large, options vidéo et son, version Android. Avantage décisif pour nous : **aucune modification de la décomp n'est redistribuée** (seule la ROM du joueur est recompilée chez lui), ce qui contourne le blocage de licence de la décomp. Point à vérifier : gba-recomp s'appuie sur une carte des fonctions par jeu, repérée par l'empreinte de la ROM ; une ROM modifiée par FE Maker n'y figurera pas. On pourrait la générer nous-mêmes, puisque la compilation de la décomp produit déjà la carte complète des symboles (fichier .map).
- **Portage natif** du moteur de la décomp sur PC (sur le modèle des portages PC réalisés par la communauté Pokémon à partir de ses décomps), qui chargerait les assets depuis la ROM de l'utilisateur.
- **Export vers Lex Talionis** (moteur Fire Emblem open source qui produit des jeux PC), si un format d'échange est réaliste.

### Alpha publique (décidée le 30/10/2026)
Public : FE Universe, dépôt rendu public. Plateforme : Windows d'abord (Linux et macOS plus tard, le code reste multiplateforme).
1. **Préalables au passage en public** : historique git vérifié (aucune ROM, aucun asset du jeu) ; position des mainteneurs de fireemblem8u sur la licence (section 2).
2. **Fonctions à faire avant le gel** (décision du 30/10/2026, dans cet ordre) : ajouter un personnage, un objet, une classe (ticket 44 étape 4), un chapitre avec une carte neuve ; formulaires des conditions et des sauts dans l'éditeur d'événements ; sprites de carte (FE-Repo et PC) ; musique (FE-Repo-Music) ; patchs de confort (phase 6, `docs/patchs-qol.md`). La carte du monde reste seulement désactivable. Décisions du 30/10/2026 : les chapitres ajoutés prennent les places libres du jeu (agrandir les tables des objets, personnages, cartes, chapitres viendra dans un second temps) ; musique : d'abord une démo simple. Chapitres ajoutés faits (page Campagne, places libres : tour, ruines, chapitres de test ; image de titre écrite d'après leur nom ; vérifié en jeu). Musique, démo faite : un MIDI importé pour la phase du joueur d'un chapitre, avec les instruments du jeu (vérifié en jeu, pas encore écouté). Reste pour la musique : les autres phases, le réglage des instruments, les morceaux de FE-Repo-Music (il faut le jeu d'instruments communautaire NIMAP2).
3. **Gel** : un hack témoin de 3 chapitres fait uniquement avec FE Maker et joué jusqu'au bout ; tickets en attente validés, playtests `tests/local` au vert, version `0.1.0-alpha`, liste des limites connues.
4. **Paquet sans Node** : release GitHub avec l'interface déjà compilée ; la décomp n'est pas dans le paquet (pas de licence) : FE Maker la télécharge au premier lancement, au commit fixé.
5. **Image Docker toute prête** sur ghcr.io (agbcc en GPL : lien vers ses sources dans CREDITS).
6. **Premier lancement guidé** : vérification de Docker (démarré, virtualisation), de mGBA et de la ROM (somme de contrôle FE8 US), avec des messages clairs.
7. **Retours des testeurs** : envoi d'un ticket en issue GitHub pré-remplie (version, onglet, journal).
8. **Docs** : guide de démarrage FR/EN, limites connues, CHANGELOG.
9. **Test sur une machine vierge** (Windows Sandbox, job CI d'installation depuis la release), tag, annonce sur FEU.
- **À faire plus tard** (retours du 30/10/2026) : musique en pause (ticket 56, sujet à creuser) ; agrandir les tables ; projet vierge : retirer aussi les classes et les armes (gardées pour l'instant, le moteur en dépend) ; idée du ticket 67 : créer un chapitre d'après une fiche au format du wiki Fire Emblem (ex. Scorched Sand : objectif, unités, terrain), pour recréer facilement un chapitre d'un autre jeu.
- **Préparé le 30/10/2026, sans rien publier** : version `0.1.0-alpha` ; étape 4 : `tools/make_release.py`, lanceurs, téléchargement de la décomp au premier lancement, workflow `release.yml` (brouillon sur tag) ; étape 5 : image étiquetée par le hash de ses sources, workflow `image.yml` ; étape 6 : `checks.py`, panneau « À installer avant de commencer » ; étape 7 : « Envoyer sur GitHub » sur un ticket (signalement pré-rempli, relu par l'utilisateur) ; étape 8 : `docs/guide.md`, `docs/guide.en.md`, `CHANGELOG.md`. Reste : le gel (étape 3), passer le dépôt en public, pousser, vérifier les workflows, test sur machine vierge, tag et annonce (décisions de l'utilisateur).
- **État** : étape 1 faite le 30/10/2026 (historique propre : 189 fichiers, code et texte seulement, fixtures fictives dès le premier commit ; mainteneurs déjà prononcés, #728). Le dépôt peut passer en public quand l'utilisateur le décide. Étape 2 : ajout de personnages fait (alliés et ennemis sur les places libres de la table du jeu, vérifié en jeu par playtest) ; armes ajoutées faites (copie d'une arme du jeu : sort et animations propres compris, 49 places ; pas les objets à usage ni les bâtons, codés par numéro) ; classes ajoutées faites (copie d'une classe du jeu, numéros 0x80 et suivants : sprites, animations, promotions ; vérifié en jeu : déplacement) ; conditions et sauts dans l'éditeur d'événements faits (tests, mémoire, étiquettes, sauts, appels, trois conditions toutes faites, retrait des blocs) ; chapitre avec carte neuve mis en attente (choix de conception à faire avec l'utilisateur) ; sprites de carte faits (FE-Repo et PC, immobile et marche, vérifié en jeu) ; patchs de confort commencés : onglet « Options du jeu » (réglages d'une nouvelle partie, ouverture passée, titre de chapitre rapide, A accélère ; vérifié en jeu) ; suite : musique, puis les autres patchs de `docs/patchs-qol.md`.

---

## 5. Exigences transverses

- **Multiplateforme** : tout doit fonctionner sous Windows, Linux et macOS. Pas de script `.bat` ou `.sh` seul : prévoir les deux ou passer par Python.
- **Installation simple** : objectif à terme, un installeur par plateforme. Prérequis tolérés au départ : Python, Docker, mGBA.
- **Tests** : tests automatiques sur la conversion projet → décomp (sans ROM, sur des données fictives). Les tests nécessitant la ROM sont lancés localement uniquement, jamais dans la CI publique.
- **CI GitHub** : lint + tests sans ROM.
- **Documentation** : guide utilisateur en français et en anglais ; guide contributeur.
- **Retours de test dans l'appli** (ajouté le 23/10/2026, sur le modèle d'un carnet d'idées) : bouton « Ticket » dans l'en-tête, toujours visible. Type (bug, idée, question), priorité, texte, captures d'écran collées avec Ctrl+V, contexte joint automatiquement (projet, onglet, fiche, unité, version du code). Liste : modifier, traité, abandonner, rouvrir, supprimer. Colonne latérale à droite (nouveau ticket en haut, tickets ouverts en dessous), l'appli reste utilisable à côté. Stockage local, hors du dépôt (dossier de réglages de FE Maker, `tickets/`) ; `python -m fe_maker.tickets` liste les tickets ouverts pour le développement.
- **Langue du code** : code et commentaires en anglais (contributeurs internationaux) ; interface en français et en anglais (choix par drapeau). L'espagnol et l'italien (faits le 23/10/2026) sont mis de côté le 30/10/2026 jusqu'à une version plus aboutie : fichiers gelés, plus chargés. Chinois et japonais envisagés.

---

## 6. Règles pour le développement assisté par IA

- Lire ce document au début de chaque session.
- Travailler **phase par phase**, ne pas anticiper les phases suivantes sans accord.
- **Ne jamais committer** : ROM, fichiers `.gba`, assets extraits de la ROM, ressources FE-Repo téléchargées. Vérifier le `.gitignore` en conséquence dès la phase 0.
- Avant de modifier la manière dont on lit une donnée de la décomp, consulter `docs/audit-decomp.md`.
- Chaque fonctionnalité terminée : test manuel en jeu décrit dans la PR ou le commit.
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

### Projets voisins à suivre (ajoutés le 20/10/2026)

- [ffta-decomp](https://github.com/charlie-troy/ffta-decomp) : décompilation de Final Fantasy Tactics Advance (GBA), axée sur la modification de l'IA. Idées à reprendre (sans code, aucune licence) :
  - une **couche de modding sans compilateur** (les réglages de l'IA sont des données éditables en CSV), proche de notre principe « données lisibles d'abord » ;
  - la **validation par exécution** : les fonctions de la ROM sont exécutées sur un processeur émulé avec des unités de test, pour prouver le comportement attendu. Piste pour nos tests (vérifier une modification de stats ou d'IA sans jouer) ;
  - une documentation précise de chaque table de données, et des corrections argumentées quand la documentation publiée se trompe ;
  - pour la phase 3 : comprendre et rendre éditable l'**IA des ennemis** de FE8.
- [gba-recomp](https://github.com/JRickey/gba-recomp) et [FFTARecomp](https://github.com/Jorge262007/FFTARecomp) : recompilation statique de jeux GBA en programmes natifs, piste principale pour la phase 7 (voir plus haut).
- [Fork de FEBuilderGBA par laqieer](https://github.com/laqieer/FEBuilderGBA) (GPL-3.0, ajouté le 24/10/2026, archivé le 20/10/2026) : version multiplateforme, outils en ligne de commande, prise en charge de la décomp en aperçu, tests en jeu sans fenêtre (idée reprise, voir phase 0).
- [« Getting Started » de FEUniverse](https://feuniverse.us/t/getting-started/10320) (ajouté le 24/10/2026) : index des tutoriels et de la documentation de FEBuilder.
- [REA](https://github.com/morluto/rea) (MIT) : outil de rétro-ingénierie piloté par des agents IA (via MCP), qui s'appuie sur Ghidra, IDA ou Hopper. Utile au **développement** de FE Maker, par exemple pour comprendre les 6,7 % de données encore binaires ou un comportement du moteur. Ce n'est pas une dépendance du logiciel. Prudence : ses chiffres de popularité affichés sont inhabituels (plus de 336 000 étoiles pour un dépôt créé en avril 2026), et son propre README met en garde contre les copies non officielles. À n'installer qu'après vérification, depuis sa source officielle.

---

## 8. Décisions en attente

- [x] Licence du code de FE Maker : GPL-3.0
- [x] Accord des mainteneurs de fireemblem8u pour la redistribution de code modifié : pas de licence, mais engagement écrit de ne pas attaquer les projets dérivés (#728, 09/01/2026) ; le risque restant vient des ayants droit du jeu, pas des mainteneurs (à peser pour les phases 6 et 7)
- [x] Framework front-end : Svelte + TypeScript
- [x] Format de patch : .ups (format habituel de la communauté et de l'auteur du projet)
- [x] Compiler les jeux créés avec les corrections `BUGFIX` de la décomp : **accepté, mais désactivé par défaut** tant que 3 blocs `BUGFIX` de la décomp ne compilent pas (option `"bugfix"` dans `fe-maker.json`, voir `docs/audit-decomp.md`)
- [ ] Proposer aux mainteneurs de la décomp les corrections des 3 blocs `BUGFIX` cassés
- [ ] Piste retenue pour la version PC
- [ ] Directions de l'interface (chantier « Interface graphique », section 4) : accueil, carte, événements, test
