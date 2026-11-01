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

## Mettre à jour

1. Dézippez la nouvelle version dans un autre dossier et lancez-la. Quand tout va bien, supprimez l'ancienne.
2. Vos projets ne bougent pas : ils sont dans `FE Maker Projects`, dans votre dossier utilisateur, hors du dossier de l'appli. Vos réglages sont gardés aussi.
3. Un projet créé par une version plus ancienne est converti à son ouverture si besoin, après une copie de `data/` dans `backups/`. Un projet enregistré par une version plus récente ne s'ouvre pas : installez cette version.
4. Une partie commencée sur un ancien essai peut ne plus marcher quand le hack a changé : testez sur une nouvelle partie.

## Créer un hack

- **Nouveau projet** : le jeu d'origine, à modifier.
- **Projet vierge** : un seul chapitre vide, sans ennemis ni dialogues, pour écrire votre histoire. Vous gardez les armes, les objets et les classes du jeu ; vous pouvez aussi retirer les personnages.

Un projet s'ouvre sur **Campagne**, le graphe de vos chapitres. La fiche d'un chapitre donne les étapes dans l'ordre : dessiner la carte, placer les unités et fixer l'objectif, écrire les dialogues, tester.

| Onglet | Pour quoi faire |
|---|---|
| Campagne | L'enchaînement des chapitres, ajouter un chapitre, terminer le jeu, la liste « À faire » |
| Chapitres | Le même chapitre en trois vues : unités et objectif, carte, dialogues |
| Personnages, Classes, Objets, Combat | Les fiches du jeu ; ajouter des personnages, des armes, des classes ; les couleurs en combat d'un personnage, tirées de son portrait ou peintes sur le sprite |
| Options du jeu | Réglages de départ, confort, options de test, ce que garde le projet |

Dans un chapitre, une **scène** est un moment du jeu : son déclencheur dit quand elle arrive (« Début du tour 3 »), son **déroulé** ce qui se passe dans l'ordre, et ses **dialogues** le texte affiché.

Un petit **i** à côté d'un titre ou d'une option donne son explication : survolez-le.

**▶ Tester** compile et lance le jeu dans mGBA. Le menu **Projet** contient **Exporter le patch**, qui donne le `.ups` à partager.

Le bouton **Ticket** de l'en-tête note un problème ; « Envoyer sur GitHub » ouvre un signalement pré-rempli, que vous relisez avant de l'envoyer.

## Limites connues de l'alpha

- Les chapitres ajoutés prennent des places libres du jeu : 21 dans un projet ordinaire, 41 dans un projet vierge.
- Armes ajoutées : copies d'une arme du jeu (49 places). Pas de nouveaux objets à usage ni de bâtons.
- Une épée, une lance ou une hache qui frappe à distance demande une animation qui a le mouvement « Attaque à distance » : la plupart des haches du jeu ne l'ont pas. Le filtre « Frappe à distance » de la bibliothèque en trouve dans le FE-Repo.
- Musique : démo seulement, un MIDI pour la phase du joueur d'un chapitre.
- Carte du monde : on peut seulement la désactiver.
- Couleurs du portrait : le résultat est approché, à retoucher au besoin ; une animation importée ne protège pas sa monture.
- Pinceaux de terrain : les raccords sont calculés d'après les tuiles du jeu ; les routes sont le point faible, et le terrain autour du trait peut changer un peu.
- « Terminer le jeu ici » ramène à l'écran titre ; le menu propose ensuite de reprendre le dernier chapitre.
- Les copies du dossier `backups/` d'un projet se restaurent à la main.
- Le jeu doit recompiler pour montrer un changement ; il n'y a pas d'aperçu en direct.

Le projet n'est pas affilié à Nintendo ni à Intelligent Systems. Ne partagez jamais de ROM : partagez le patch.
