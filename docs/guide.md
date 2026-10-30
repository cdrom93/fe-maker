# Guide de démarrage de FE Maker (alpha)

FE Maker est un éditeur simple pour créer un rom hack de Fire Emblem: The Sacred Stones (FE8, version américaine). Il travaille sur la décomp du jeu, pas sur la ROM : vos changements sont du code recompilé, et votre hack se partage en patch `.ups`.

## Ce qu'il vous faut

- **Windows 10 ou 11** (Linux et macOS viendront plus tard).
- **Python 3.10 ou plus** : https://www.python.org/downloads/ (cochez « Add Python to PATH » à l'installation).
- **Docker Desktop**, démarré : il compile le jeu. S'il ne démarre pas, la virtualisation (Intel VT-x, AMD-V) est sans doute coupée dans le BIOS.
- **mGBA**, pour tester : https://mgba.io/downloads.html
- **Votre ROM** de Fire Emblem: The Sacred Stones (USA, Australia), obtenue légalement. FE Maker ne la distribue pas et vérifie sa somme de contrôle.

## Installer et lancer

1. Dézippez `fe-maker-<version>.zip` où vous voulez.
2. Lancez `lancer-fe-maker.bat`. Le premier lancement installe ce qu'il faut, puis ouvre l'interface dans votre navigateur.
3. Donnez votre ROM. L'accueil indique ce qui manque encore : le bouton « Télécharger » récupère le code du jeu (quelques minutes, une seule fois).
4. La première compilation prépare les outils : elle peut prendre plusieurs minutes.

## Créer un hack

- **Nouveau projet** : le jeu d'origine, à modifier.
- **Projet vierge** : un seul chapitre vide, sans ennemis ni dialogues, pour écrire votre histoire. Vous gardez les armes, les objets et les classes du jeu ; vous pouvez aussi retirer les personnages.

Les onglets :

| Onglet | Pour quoi faire |
|---|---|
| Personnages, Classes, Objets, Combat | Les fiches du jeu ; ajouter des personnages, des armes, des classes |
| Chapitres | Unités, inventaires, objectif, renforts |
| Campagne | L'enchaînement des chapitres ; ajouter un chapitre, terminer le jeu |
| Cartes | Peindre, importer ou exporter vers Tiled |
| Dialogues | Conversations, soutiens, scènes et leurs événements (bouton ⚙ d'une scène) |
| Options du jeu | Réglages de départ, confort, options de test |

**▶ Tester** compile et lance le jeu dans mGBA. **Exporter le patch** donne le `.ups` à partager.

Le bouton **Ticket** de l'en-tête note un problème ; « Envoyer sur GitHub » ouvre un signalement pré-rempli, que vous relisez avant de l'envoyer.

## Limites connues de l'alpha

- Les chapitres ajoutés prennent des places libres du jeu : 21 dans un projet ordinaire, 41 dans un projet vierge.
- Armes ajoutées : copies d'une arme du jeu (49 places). Pas de nouveaux objets à usage ni de bâtons.
- Personnages et classes ajoutés : la description vient du modèle ou reste vide.
- Musique : démo seulement, un MIDI pour la phase du joueur d'un chapitre.
- Carte du monde : on peut seulement la désactiver.
- Images de titre générées : encore assez loin du style du jeu.
- Le jeu doit recompiler pour montrer un changement ; il n'y a pas d'aperçu en direct.

Le projet n'est pas affilié à Nintendo ni à Intelligent Systems. Ne partagez jamais de ROM : partagez le patch.
