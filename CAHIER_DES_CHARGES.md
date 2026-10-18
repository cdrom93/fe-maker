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

---

## 2. Cadre légal et licences (à respecter strictement)

Le projet doit pouvoir vivre publiquement sur GitHub sans risque. Règles :

1. **Aucune donnée Nintendo dans le dépôt.** Pas de ROM, pas d'assets extraits, pas de fichiers générés à partir de la ROM.
2. **L'utilisateur fournit sa propre ROM** (FE8 US, vérifiée par SHA1 `c25b145e37456171ada4b0d440bf88a19f4d509f`) au premier lancement. L'outil refuse toute autre ROM avec un message clair.
3. **La décomp FE8 est un sous-module Git**, jamais copiée dans notre dépôt.
4. **Partage des jeux créés sous forme de patch** (.ups ou .bps) à appliquer sur sa propre ROM, jamais de .gba complet distribué par l'outil.
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
   | Décomp fireemblem8u | **Aucun fichier LICENSE trouvé** à la racine du dépôt | Par défaut, sans licence = tous droits réservés. On l'utilise **uniquement comme sous-module non modifié**. Toute redistribution de code modifié de la décomp (modules moteur, phase 6, version PC) est **bloquée tant que les mainteneurs n'ont pas donné leur accord écrit** (ouvrir une issue sur leur dépôt) |
   | FE-Repo (graphismes) | F2E ou F2U selon la ressource, F2U par défaut | Voir point 5 |
   | FE-Repo-Music | À vérifier | Même règles que FE-Repo tant que non vérifié |
   | Lex Talionis | À vérifier | Inspiration ergonomique uniquement, aucune reprise de code sans vérification |

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
- **Front-end** : à choisir lors de la phase 0 (proposition : Svelte ou React + TypeScript). Critère principal : simplicité.
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

### Phase 0 — Audit et fondations
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

### Phase 1 — POC : personnages et objets
**Objectif : valider toute la chaîne de bout en bout sur les données les plus simples.**
- Premier lancement : sélection de la ROM, vérification SHA1.
- Création d'un projet FE Maker.
- **Éditeur d'objets** : nom, type d'arme, puissance, précision, critique, poids, portée, durabilité, prix, icône.
- **Éditeur de personnages** : nom, classe, niveau de départ, stats de base, taux de croissance, rangs d'armes, inventaire de départ, portrait (aperçu).
- Conversion projet → décomp, compilation Docker, génération du .gba et du patch .ups.
- Bouton « Tester » qui lance mGBA.
- **Critère de réussite** : je modifie un personnage dans l'interface, je clique sur « Tester », je vois la modification en jeu.

### Phase 2 — Classes et système de combat
- Éditeur de classes : stats de base et maximales, mouvement, type de déplacement, armes utilisables, promotions, compétences.
- Triangle des armes, efficacités (armes anti-cavalerie, anti-volants…).
- Aperçu de la fiche personnage complète (perso + classe).

### Phase 3 — Chapitres
- Liste et ordre des chapitres, objectifs (déroute, boss, survie, s'emparer…).
- **Placement des unités** sur les cartes existantes : alliés, ennemis, renforts, IA des ennemis, par glisser-déposer sur un aperçu de la carte.
- **Éditeur de cartes** : peinture de tuiles à partir des tilesets, terrains, import de cartes depuis FE-Repo.

### Phase 4 — Dialogues et événements
- Éditeur de dialogues avec aperçu (portraits, position, émotions).
- Éditeur d'événements **visuel** (blocs ou formulaires, pas de code) : début/fin de chapitre, recrutements, villages, conversations, conditions de victoire.
- Soutiens entre personnages.
- Textes : gestion multilingue.

### Phase 5 — Bibliothèque de ressources communautaires
- Navigateur intégré de FE-Repo (portraits, animations de combat, sprites de carte, icônes, cartes, tilesets, décors) avec aperçus.
- Exploiter `file_urls.json` du dépôt FE-Repo comme index si le format s'y prête.
- Téléchargement à la demande, conversion automatique au format GBA (palette, taille), gestion des licences F2E/F2U et des crédits (voir section 2).
- Import de ressources personnelles (PNG) avec conversion et vérification de palette.
- Musique (FE-Repo-Music) : à étudier, format plus complexe.

### Phase 6 — Édition avancée et moteur
- « Mode expert » : accès au code C de la décomp depuis l'outil, système de modules/patchs moteur réutilisables (ex. compétences, nouvelles mécaniques).
- Partage de modules entre utilisateurs.

### Phase 7 — Version PC (à redéfinir)
Deux pistes à évaluer le moment venu :
- **Portage natif** du moteur de la décomp sur PC (sur le modèle des portages PC réalisés par la communauté Pokémon à partir de ses décomps), qui chargerait les assets depuis la ROM de l'utilisateur.
- **Export vers Lex Talionis** (moteur Fire Emblem open source qui produit des jeux PC), si un format d'échange est réaliste.

---

## 5. Exigences transverses

- **Multiplateforme** : tout doit fonctionner sous Windows, Linux et macOS. Pas de script `.bat` ou `.sh` seul : prévoir les deux ou passer par Python.
- **Installation simple** : objectif à terme, un installeur par plateforme. Prérequis tolérés au départ : Python, Docker, mGBA.
- **Tests** : tests automatiques sur la conversion projet → décomp (sans ROM, sur des données fictives). Les tests nécessitant la ROM sont lancés localement uniquement, jamais dans la CI publique.
- **CI GitHub** : lint + tests sans ROM.
- **Documentation** : guide utilisateur en français et en anglais ; guide contributeur.
- **Langue du code** : code et commentaires en anglais (contributeurs internationaux) ; interface traduite.

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

---

## 8. Décisions en attente

- [x] Licence du code de FE Maker : GPL-3.0
- [ ] Accord des mainteneurs de fireemblem8u pour la redistribution de code modifié (bloquant pour phases 6 et 7)
- [ ] Framework front-end
- [ ] Format de patch par défaut (.ups ou .bps)
- [ ] Piste retenue pour la version PC
