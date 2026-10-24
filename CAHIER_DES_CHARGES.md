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
   | Décomp fireemblem8u | **Aucun fichier LICENSE trouvé** à la racine du dépôt | Par défaut, sans licence = tous droits réservés. On l'utilise **uniquement comme sous-module non modifié**. Toute redistribution de code modifié de la décomp (modules moteur, phase 6, version PC) est **bloquée tant que les mainteneurs n'ont pas donné leur accord écrit** (ouvrir une issue sur leur dépôt) |
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

### Phase 3 — Chapitres 🚧 (en cours)
> Fait le 20/10/2026 : onglet Chapitres en lecture seule (liste des 79 chapitres, carte rendue fidèlement, unités sur la carte avec leurs sprites, groupes : joueur / scène d'ouverture / renforts par tour, fiche d'unité cliquable avec classe, niveau et inventaire). Puis, le même jour : unités éditables (glisser-déposer sur la carte, classe, niveau, inventaire de départ) ; seuls les groupes modifiés sont stockés dans `data/chapters.json` et réécrits dans la décomp, et les 729 groupes du jeu passent l'aller-retour sans changement. Le 23/10/2026 : ajout, duplication et suppression d'unités (une unité ajoutée copie l'IA et les réglages d'une unité existante, sans son trajet d'entrée), choix du personnage de l'unité, contrôles (case occupée, limites du moteur par camp, personnage manquant) ; aller-retour vérifié sur les 663 groupes non vides du jeu. Liste des classes avec leurs sprites de carte. Puis IA des unités : comportement en un choix (poursuit, attaque à portée, garde sa position, soigne, pille…), réglages détaillés (action, déplacement, choix de la cible, repli pour se soigner, garde sa case), libellés tirés de FEBuilderGBA ; aller-retour vérifié sur tous les groupes du jeu et projet de test compilé. Puis, à partir des premiers tickets (23/10/2026) : unités du combat séparées des unités de cinématique (repérées automatiquement, masquées par défaut, avertissement sur leur fiche) ; groupe d'unités ouvrable (liste de ses unités) ; option de test « Prologue simplifié » (sans cinématique, unités directement en place, vérifiée en jeu) ; triangle des armes dessiné (armes et magie, valeurs sur les flèches) ; listes d'efficacité nommées avec les armes qui les utilisent. Puis objectifs de chapitre : s'emparer d'une case (choisie sur la carte), vaincre tous les ennemis, vaincre le chef, survivre N tours ; texte de l'écran de statut ; fenêtre d'objectif et événements de victoire réécrits ensemble. 50 chapitres sur 79 modifiables ; les objectifs scriptés (escortes, zones, cartes spéciales) restent affichés en lecture seule. Vérifié en jeu : fenêtre « Seize throne » après changement du prologue. Tickets 8 à 11 (23/10/2026) : la classe d'un personnage nommé vient uniquement de sa fiche (plus de classe par chapitre, sauf pour les unités génériques) ; listes avec une section repliée pour les éléments rares (personnages génériques, classes jamais utilisées, cartes sans titre) ; tickets dans une colonne latérale. Puis (23/10/2026) : chef du chapitre visible et modifiable (objectif « Vaincre le chef ») ; prise de case validée en jeu par l'utilisateur ; arme « réservée à personne » = arme libre ; classes utilisées par le projet sorties des sections « jamais utilisées » ; bandeau du haut fixe. Puis éditeur de cartes (23/10/2026) : onglet « Cartes » (69 cartes, nommées d'après leurs chapitres), palette des tuiles du jeu de tuiles de la carte (doublons masqués, filtre par terrain), outils crayon, rectangle, remplissage et pipette (clic droit), grille, zoom, calque des terrains avec légende ; noms de terrains clairs et traduits (le nom en jeu est affiché à côté) ; une carte peinte est stockée dans `data/maps.json` et réécrite dans la décomp (`.mar`), l'onglet Chapitres affiche la carte peinte et y renvoie. Correction au passage : un projet non modifié rebâtit de nouveau la ROM d'origine (la Mani Katti, réservée à personne dans le jeu, était débloquée depuis le ticket 12). Puis, le même jour : taille de la carte (lignes et colonnes ajoutées ou retirées à droite et en bas, limites du moteur contrôlées) ; changements de carte (portes, villages, murs) affichés, modifiables (tuiles « après », position, taille, numéro), ajoutés et supprimés ; avertissements quand une unité se retrouve hors de la carte ou sur un terrain que sa classe ne peut pas traverser, ou quand la case à prendre sort de la carte (seulement ce que le projet a changé : le jeu d'origine a ses propres cas) ; ticket 14 : planche complète du jeu de tuiles et blocs de plusieurs tuiles (pris dans la palette ou copiés sur la carte au clic droit glissé). Puis (23/10/2026, priorité de l'utilisateur) : objets de carte automatiques. FE Maker reconnaît par leur terrain les villages, maisons, coffres, portes, murs fissurés et bois morts posés sur la carte ; pour un objet nouveau, il crée tout seul le changement de carte (état « après » appris sur les changements du jeu d'origine pour chaque jeu de tuiles : changement entier quand l'objet ressemble à un original, ombres des murs comprises, sinon tuile par tuile, sinon même image dans un autre jeu de tuiles, tuile la plus ressemblante ou sol voisin) et l'événement de lieu (coffre avec son objet ou son or, porte, village avec cadeau, portrait de villageois et message, maison avec message ; textes ajoutés au jeu). Les objets d'origine gardent leur comportement, mais leur contenu peut être changé ; un objet effacé perd son événement. Liste des objets de la carte, outil « Objets », aperçu « après ». Sur les cartes d'origine, l'état « après » est retrouvé pour tous les objets (et identique au changement du jeu dans 149 cas sur 175). Projet avec coffre, village, maison et porte ajoutés compilé ; pas encore testé en jeu. Puis ticket 15 (23/10/2026) : tourner et retourner une tuile ou un bloc de tuiles (miroirs, demi-tour, quarts de tour) ; les nouvelles tuiles sont ajoutées au jeu de tuiles dans ses emplacements libres (quarts de tour : nouveaux dessins 8 × 8, réutilisés quand un dessin existant retourné convient), visibles aussitôt dans la palette, compilés (tests locaux) ; pas encore testé en jeu. Reste pour les cartes : import depuis FE-Repo (phase 5), modification du terrain d'une tuile, nouvelle couche de changements pour une carte qui n'en a pas (seulement des cartes de cinématique). Puis magasins : une armurerie ou un magasin posé sur la carte reçoit sa liste d'objets en vente (modifiable, magasin secret avec carte de membre possible), compilé. Puis terrain d'une tuile : la tuile choisie (ou le bloc) peut recevoir un autre terrain ; FE Maker en fait une copie dans un emplacement libre, pour ne pas changer les autres cartes du même jeu de tuiles. Les tests locaux avec la ROM passent le 23/10/2026 (ROM d'origine reconstruite octet pour octet ; projet modifié, unités ajoutées et supprimées, carte peinte et agrandie, changements de carte modifiés et ajoutés compris, compilé avec un patch .ups correct). Test en jeu à faire. Ticket 18 (24/10/2026) : tourner une tuile que le jeu de tuiles a déjà dans ce sens réutilise la tuile existante ; et quand le jeu l'a redessinée (ponts, routes : la lumière vient toujours du même côté, environ un tiers des pixels diffèrent), FE Maker propose d'utiliser la tuile du jeu plutôt que la copie tournée. Ticket 17 (24/10/2026) : les listes d'objets (inventaires, coffres, villages, magasins) montrent les icônes et ont un champ de recherche (nom ou type d'arme, sans tenir compte des accents), au clavier aussi. Ticket 16 (24/10/2026) : chaque carte peut prendre une autre palette de son jeu de tuiles parmi celles que le jeu utilise avec lui (saisons, désert, nuit, ruines… de 1 à 4 selon le jeu de tuiles), avec un aperçu des couleurs et les chapitres qui l'utilisent ; la carte et la palette de tuiles se redessinent aussitôt, l'onglet Chapitres aussi, et la compilation change la palette de tous les chapitres de la carte. Pas encore testé en jeu (Docker était en panne ce jour-là). Ticket 19 (24/10/2026) : le passage créé par un bois mort coupé ou un mur cassé (et l'état « après » de tout objet nouveau) peut être dessiné à la main, en semi-automatique : FE Maker part de sa proposition, en fait un changement du projet ouvert aussitôt, qu'on peint et qu'on peut agrandir ; ce changement compte pour l'objet quelles que soient ses tuiles. Un objet qui a déjà son changement propose de l'ouvrir. Corrigé au passage : « Ajouter un changement » n'ouvrait pas le changement ajouté. Ticket 21 (24/10/2026) : chaque carte peut être dessinée avec un autre des 11 jeux de tuiles du jeu (« Jeu de tuiles », vignettes et chapitres qui l'utilisent). Les dessins, les terrains, les animations (eau) et la palette suivent ; la carte et ses changements sont redessinés case par case selon le terrain (la tuile la plus courante de ce terrain dans le nouveau jeu de tuiles), donc la carte se joue pareil et il ne reste qu'à la retoucher ; les terrains que le nouveau jeu de tuiles n'a pas sont signalés. Annulable ; la compilation change le jeu de tuiles de tous les chapitres de la carte. Compilé le 24/10/2026 (tests locaux), pas encore testé en jeu. Ticket 29 (24/10/2026) : convoi. Fiche personnage, « Ouvre le convoi » (le personnage et les unités à côté de lui ont la commande « Convoi » ; dans le jeu, Eirika et Ephraïm) ; onglet Chapitres, « Convoi disponible dans ce chapitre » (le jeu n'en a pas au prologue, aux chapitres 1 et 5x ni au château de Frelia). Le moteur n'est réécrit que si le projet change ces réglages. Corrigé au passage : la capacité « Accès au convoi » de la fiche était en fait l'attribut `CA_SUPPLY` de FE7 (porteur du convoi, qui n'ouvre rien dans FE8), renommée « Porteur du convoi (FE7) ». Ticket 26 : choix de la classe avec recherche, sprites de carte et signe du genre (fiche personnage et unités des chapitres). Compilé le 24/10/2026, pas encore testé en jeu.
- Liste et ordre des chapitres, objectifs (déroute, boss, survie, s'emparer…).
- **Placement des unités** sur les cartes existantes : alliés, ennemis, renforts, IA des ennemis, par glisser-déposer sur un aperçu de la carte.
- **Éditeur de cartes** : peinture de tuiles à partir des tilesets, terrains, import de cartes depuis FE-Repo.
- **Changements de carte automatiques** (demande de l'utilisateur, 23/10/2026, priorité) : régler les couches de changements à la main est trop pénible. On dessine la carte, on pose un coffre, un village à visiter, une porte, un mur fissuré… et FE Maker crée tout seul le changement (état « après » : coffre ouvert, village fermé, porte ouverte, décombres), sa position, son numéro et ce qu'il faut pour qu'il fonctionne (événements de village, contenu du coffre), au moins pour les cas classiques. But : dessiner la carte simplement et qu'elle fonctionne quasiment toute seule. Le réglage manuel des changements reste disponible pour les cas particuliers.

### Phase 4 — Dialogues et événements 🚧 (commencée le 23/10/2026)
> Fait le 23/10/2026 : onglet « Dialogues ». Pour chaque chapitre, les scènes qui affichent des messages, rangées par ce qui les déclenche (début, tour N du joueur ou de l'ennemi, conversation A → B, village, maison, zone, autre événement, fin, tutoriels repliés ; une scène appelée par une autre prend son déclencheur). Chaque message se lit en étapes : portrait qui entre (8 positions du jeu), sort ou se déplace, répliques (une ligne vide = nouvelle bulle après un bouton ; expressions en un clic : sourire, bouche immobile, yeux mi-clos ou fermés, clin d'œil) ; aperçu de l'écran à chaque étape avec les vrais portraits aux positions du jeu. Les 3404 messages du jeu passent l'aller-retour lecture → écriture sans changement ; seuls les messages modifiés sont réécrits. Lien depuis la fiche du chapitre. Puis répliques de combat (un personnage contre un autre ou contre n'importe qui, une fois par chapitre) et dernières paroles (par chapitre ou pour tous les chapitres) : celles du jeu se modifient comme les autres dialogues, et on peut en ajouter. Puis nouvelles conversations : un personnage peut « Parler » à un autre (ou dans les deux sens), avec son dialogue, et le second peut rejoindre l'armée (script sur le modèle des recrutements du jeu : musique de recrutement, texte, `CUSA`). Puis scènes de tour : un dialogue au début du tour N du joueur, de l'ennemi ou des alliés. Puis renforts (onglet Chapitres) : un nouveau groupe d'unités arrive au début du tour N d'un camp, avec la routine de renforts du jeu (caméra sur les unités). Puis objectifs : « Atteindre une zone » (tracée sur la carte ; n'importe quelle unité du joueur ou un personnage précis) et « Personnage à protéger » (la partie est perdue s'il meurt, icône de protection ; se combine avec tous les objectifs). Compilé (tests locaux), pas encore testé en jeu. Le 24/10/2026 (ticket 20 : un texte trop long cassait la bulle en jeu) : mise en page automatique. Les lignes trop larges pour la bulle (208 pixels en conversation, 144 pour les répliques de combat et de mort, mesurés avec les largeurs des lettres de la police du jeu) sont coupées entre les mots à la compilation, et une bulle qui dépasse deux lignes ainsi est coupée en bulles de deux lignes ; l'aperçu dessine les bulles avec la vraie police du jeu, une bulle après l'autre, et un lien écrit la coupure dans le texte. Les lettres accentuées sont maintenant permises (la police US les a : é, è, à, ç, ñ, ¿…) dans les dialogues, les noms et les textes d'objectif ; seuls les caractères absents de la police sont signalés. Pas encore testé en jeu. Puis soutiens (24/10/2026) : entrée « Soutiens » de l'onglet Dialogues, avec les 83 paires du jeu ; pour chaque paire, les points au départ et les points gagnés à chaque tour commencé côte à côte (avec le nombre de tours pour atteindre C, B et A), et ses trois conversations C, B et A, qui se modifient comme les autres dialogues. On peut ajouter une paire (ses trois conversations sont créées avec les portraits des deux personnages) ou en retirer une ; FE Maker réécrit seulement les listes de soutien des personnages concernés, crée la liste d'un personnage qui n'en avait pas et ajoute la paire à la table des conversations. Contrôles : 7 partenaires au plus, paires en double, conversations manquantes, soutien qui n'atteint jamais C. Lien depuis la fiche personnage. Pas encore compilé (Docker en panne ce jour-là ; l'overlay est généré sans erreur) ni testé en jeu. Puis objectif combiné (24/10/2026) : « Survivre N tours ou vaincre le chef » (case « ou vaincre le chef » de l'objectif de survie) ; les quatre chapitres du jeu écrits ainsi (Hamill Canyon, et les escortes de Mansel et de Duessel, qui ont aussi leur personnage à protéger) deviennent modifiables. Les objectifs encore en lecture seule sont ceux de la tour de Valni et des ruines de Lagdou (monstres tirés au hasard). Au passage, les messages générés des villages et maisons sont coupés avec la police du jeu, et les textes d'objectif comptent les lettres accentuées comme un seul octet. Puis éditeur d'événements visuel, première version (24/10/2026) : le bouton ⚙ d'une scène (onglet Dialogues) ouvre son script en blocs, un par commande, joués de haut en bas : musique, dialogue (avec ou sans décor, ouvrable, première ligne affichée), groupe d'unités qui arrive, déplacement d'une unité, curseur et caméra, attente, fondus, décor, unité retirée, unité qui rejoint l'armée, drapeaux… avec des listes pour les musiques, les décors, les personnages et les groupes du chapitre. On peut modifier, déplacer, retirer et ajouter des commandes ; les commandes avancées (conditions, sauts, appels) sont gardées telles quelles et peuvent être déplacées ou retirées. Les 1234 scripts du jeu se lisent et se réécrivent sans perte ; seul un script modifié est réécrit. Pas encore compilé (Docker en panne) ni testé en jeu. Les scripts sans dialogue lancés par les événements du chapitre (renforts, événements de tour, zones…) sont listés aussi. Reste : des formulaires pour les commandes avancées, l'ajout de scènes à n'importe quel déclencheur.

- Éditeur de dialogues avec aperçu (portraits, position, émotions).
- Éditeur d'événements **visuel** (blocs ou formulaires, pas de code) : début/fin de chapitre, recrutements, villages, conversations, conditions de victoire.
- **Objectifs scriptés** (demande de l'utilisateur, 23/10/2026) : rendre modifiables les objectifs que la phase 3 affiche en lecture seule — escorte (protéger un personnage), zones à atteindre, « survivre N tours ou vaincre le chef », conditions combinées, cartes spéciales — et pouvoir en créer de nouveaux de ce type.
- Soutiens entre personnages.
- Textes : gestion multilingue.

### Phase 5 — Bibliothèque de ressources communautaires
> Commencée le 24/10/2026 : import de portraits personnels. Fiche personnage, « Portrait n° N : remplacer par une image » : une planche PNG de 128 × 112 pixels, 16 couleurs au plus, au format des portraits de FE-Repo et FEBuilderGBA (disposition lue dans le code de FEBuilderGBA), remplace le portrait du jeu (visage, yeux mi-clos et fermés, six bouches, mini-portrait, palette). La place de la bouche et des yeux est trouvée toute seule (exacte sur les 86 portraits du jeu) et reste réglable ; la planche actuelle se télécharge comme modèle ; les aperçus de toute l'appli (dialogues compris) montrent le nouveau portrait. Contrôles : taille, nombre de couleurs, parties de l'image que le jeu ne montre pas. Pas encore compilé (Docker en panne) ni testé en jeu. Puis navigateur FE-Repo pour les portraits (24/10/2026) : « Chercher dans FE-Repo » dans le panneau du portrait. FE Maker lit l'index du dépôt (`file_urls.json`, gardé une semaine, réutilisé hors ligne), cherche par nom, jeu, dossier ou artiste, montre les vignettes, les auteurs et la licence lue dans le nom du fichier (`[F2E]`, sinon F2U comme le conseille le dépôt) ; « Utiliser » télécharge la planche (gardée en cache) et l'importe, et les auteurs sont écrits tout seuls dans le CREDITS.txt du projet (retirés quand le portrait est retiré). Testé avec un index simulé, puis avec le vrai dépôt. Ticket 28 (24/10/2026) : FE-Repo se parcourt librement (choix du dossier, avec le nombre de portraits, filtre « F2E seulement », pages de 120, « Afficher plus ») ; le nom du personnage n'est plus qu'une suggestion de recherche ; les fichiers qui ne sont pas des planches de 128 × 112 (pièces détachées, tutoriels) sont affichés sans déformation, en fin de liste, et ne peuvent pas être importés. Nouveaux portraits (24/10/2026) : « Nouveau portrait pour ce personnage » (planche PNG ou FE-Repo) ajoute un portrait après ceux du jeu (n° 173 et suivants, 254 au plus) au lieu de remplacer celui du jeu, qui sert parfois à d'autres personnages ; le personnage le prend aussitôt. Il a un nom (modifiable), apparaît dans les dialogues comme les autres et peut être supprimé (le personnage qui l'utilise est alors signalé). Compilé le 24/10/2026 (tests locaux), pas encore testé en jeu. Reste : les autres ressources (sprites de carte, animations, icônes, cartes) dans le même navigateur.
- Navigateur intégré de FE-Repo (portraits, animations de combat, sprites de carte, icônes, cartes, tilesets, décors) avec aperçus.
- Exploiter `file_urls.json` du dépôt FE-Repo comme index si le format s'y prête.
- Téléchargement à la demande, conversion automatique au format GBA (palette, taille), gestion des licences F2E/F2U et des crédits (voir section 2).
- Import de ressources personnelles (PNG) avec conversion et vérification de palette.
- Musique (FE-Repo-Music) : à étudier, format plus complexe.

### Phase 6 — Édition avancée et moteur
- « Mode expert » : accès au code C de la décomp depuis l'outil, système de modules/patchs moteur réutilisables (ex. compétences, nouvelles mécaniques).
- Partage de modules entre utilisateurs.

### Phase 7 — Version PC (à redéfinir)
Trois pistes à évaluer le moment venu :
- **Recompilation statique de la ROM produite** avec [gba-recomp](https://github.com/JRickey/gba-recomp) (MIT/Apache-2.0) : l'outil traduit à l'avance une ROM GBA en programme natif (Windows, Linux, macOS), avec un modèle matériel complet (affichage, son, sauvegardes, manettes). [FFTARecomp](https://github.com/Jorge262007/FFTARecomp) montre le résultat visé pour un jeu tactique : installeur « choisissez votre ROM, cliquez », écran large, options vidéo et son, version Android. Avantage décisif pour nous : **aucune modification de la décomp n'est redistribuée** (seule la ROM du joueur est recompilée chez lui), ce qui contourne le blocage de licence de la décomp. Point à vérifier : gba-recomp s'appuie sur une carte des fonctions par jeu, repérée par l'empreinte de la ROM ; une ROM modifiée par FE Maker n'y figurera pas. On pourrait la générer nous-mêmes, puisque la compilation de la décomp produit déjà la carte complète des symboles (fichier .map).
- **Portage natif** du moteur de la décomp sur PC (sur le modèle des portages PC réalisés par la communauté Pokémon à partir de ses décomps), qui chargerait les assets depuis la ROM de l'utilisateur.
- **Export vers Lex Talionis** (moteur Fire Emblem open source qui produit des jeux PC), si un format d'échange est réaliste.

---

## 5. Exigences transverses

- **Multiplateforme** : tout doit fonctionner sous Windows, Linux et macOS. Pas de script `.bat` ou `.sh` seul : prévoir les deux ou passer par Python.
- **Installation simple** : objectif à terme, un installeur par plateforme. Prérequis tolérés au départ : Python, Docker, mGBA.
- **Tests** : tests automatiques sur la conversion projet → décomp (sans ROM, sur des données fictives). Les tests nécessitant la ROM sont lancés localement uniquement, jamais dans la CI publique.
- **CI GitHub** : lint + tests sans ROM.
- **Documentation** : guide utilisateur en français et en anglais ; guide contributeur.
- **Retours de test dans l'appli** (ajouté le 23/10/2026, sur le modèle d'un carnet d'idées) : bouton « Ticket » dans l'en-tête, toujours visible. Type (bug, idée, question), priorité, texte, captures d'écran collées avec Ctrl+V, contexte joint automatiquement (projet, onglet, fiche, unité, version du code). Liste : modifier, traité, abandonner, rouvrir, supprimer. Colonne latérale à droite (nouveau ticket en haut, tickets ouverts en dessous), l'appli reste utilisable à côté. Stockage local, hors du dépôt (dossier de réglages de FE Maker, `tickets/`) ; `python -m fe_maker.tickets` liste les tickets ouverts pour le développement.
- **Langue du code** : code et commentaires en anglais (contributeurs internationaux) ; interface traduite en français, anglais, espagnol et italien (choix par drapeau ; 23/10/2026). Chinois et japonais envisagés.

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
- [REA](https://github.com/morluto/rea) (MIT) : outil de rétro-ingénierie piloté par des agents IA (via MCP), qui s'appuie sur Ghidra, IDA ou Hopper. Utile au **développement** de FE Maker, par exemple pour comprendre les 6,7 % de données encore binaires ou un comportement du moteur. Ce n'est pas une dépendance du logiciel. Prudence : ses chiffres de popularité affichés sont inhabituels (plus de 336 000 étoiles pour un dépôt créé en avril 2026), et son propre README met en garde contre les copies non officielles. À n'installer qu'après vérification, depuis sa source officielle.

---

## 8. Décisions en attente

- [x] Licence du code de FE Maker : GPL-3.0
- [ ] Accord des mainteneurs de fireemblem8u pour la redistribution de code modifié (bloquant pour phases 6 et 7)
- [x] Framework front-end : Svelte + TypeScript
- [x] Format de patch : .ups (format habituel de la communauté et de l'auteur du projet)
- [x] Compiler les jeux créés avec les corrections `BUGFIX` de la décomp : **accepté, mais désactivé par défaut** tant que 3 blocs `BUGFIX` de la décomp ne compilent pas (option `"bugfix"` dans `fe-maker.json`, voir `docs/audit-decomp.md`)
- [ ] Proposer aux mainteneurs de la décomp les corrections des 3 blocs `BUGFIX` cassés
- [ ] Piste retenue pour la version PC
