# Guide de démarrage de FE Maker (alpha)

FE Maker est un éditeur simple pour créer un rom hack de Fire Emblem: The Sacred Stones (FE8, version américaine). Il travaille sur la décomp du jeu, pas sur la ROM : vos changements sont du code recompilé, et votre hack se partage en patch `.ups`.

## Ce qu'il vous faut

- **Windows 10 ou 11** (Linux et macOS viendront plus tard).
- **mGBA**, pour tester : FE Maker l'installe pour vous depuis l'accueil (sinon : https://mgba.io/downloads.html).
- **Votre ROM** de Fire Emblem: The Sacred Stones (USA, Australia), obtenue légalement. FE Maker ne la distribue pas et vérifie sa somme de contrôle.

## Installer et lancer

1. Téléchargez `fe-maker-setup-<version>.exe` (page des versions du dépôt) et lancez-le. Pas besoin d'être administrateur. Windows peut afficher « Windows a protégé votre ordinateur » (l'installateur n'est pas signé) : « Informations complémentaires », puis « Exécuter quand même ».
2. L'installateur crée « FE Maker » dans le menu Démarrer et sur le bureau, puis le lance : l'interface s'ouvre dans votre navigateur. La petite fenêtre noire réduite dans la barre des tâches est le serveur de FE Maker : la fermer quitte FE Maker.
   Sans installateur : dézippez `fe-maker-<version>.zip` et lancez `lancer-fe-maker.bat` (il faut alors Python 3.10 ou plus, https://www.python.org/downloads/).
3. Donnez votre ROM. L'accueil indique ce qui manque encore : les boutons « Télécharger » récupèrent le code du jeu et les outils de compilation (quelques minutes, une seule fois). Rien d'autre à installer : pas besoin de Docker.
4. FE Maker lance alors tout seul la première compilation du jeu, en arrière-plan (une dizaine de minutes, une seule fois) : vous pouvez travailler pendant ce temps. Ensuite, un test se compile en moins de deux minutes.

## Mettre à jour

1. FE Maker propose lui-même la nouvelle version quand elle sort : un clic l'installe et le relance. Vous pouvez aussi lancer l'installateur de la nouvelle version par-dessus l'ancienne.
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
| Chapitres | Le même chapitre en trois vues : unités et objectif, carte, dialogues ; ses réglages (météo, fond de combat, caméra, brouillard…) sont repliés en bas |
| Personnages, Classes, Objets, Combat | Les fiches du jeu ; ajouter des personnages, des armes, des classes ; les couleurs en combat d'un personnage, tirées de son portrait ou peintes sur le sprite |
| Options du jeu | Règles (force et magie séparées, compétences...), réglages de départ, confort, fiches des unités, ce que garde le projet (les options de test sont dans **FE Maker** > **Options**) |

Dans un chapitre, un **évènement** est un moment du jeu : son déclencheur dit quand il arrive (« Début du tour 3 »), son **déroulé** ce qui se passe dans l'ordre, et ses **dialogues** le texte affiché. Un évènement peut venir à un tour ou sur plusieurs tours, en parlant, quand une unité s'arrête dans une zone ou d'après un souvenir. Les **répliques** (en combat, à la mort) ne sont pas des évènements.

Un petit **i** à côté d'un titre ou d'une option donne son explication : survolez-le.

**▶ Tester** compile et lance le jeu dans mGBA. Le menu **Fichier**, qui s'ouvre en cliquant sur **FE Maker** en haut à gauche comme dans les logiciels de bureautique, contient **Exporter le patch**, qui donne le `.ups` à partager. Tout s'enregistre au fur et à mesure (Ctrl+S force l'enregistrement) ; le même menu propose aussi **Nouveau projet**, **Ouvrir** (les projets récents, ou **Ouvrir un autre projet…** qui ouvre la fenêtre de choix de dossier : aucun chemin à taper), **Enregistrer sous…** (une copie dans un autre dossier), **Renommer…**, **Ouvrir le dossier du projet**, **Fermer le projet**, **Options…** (une fenêtre par catégories : **Émulateur** pour les touches, le son, la pause hors de la fenêtre, l'avance rapide, la taille de la fenêtre, le plein écran, le retour en arrière et le lissage, chacun laissé au choix de mGBA tant qu'on n'y touche pas ; **Ce projet** pour les retours au jeu d'origine, le début des tests et le prologue simplifié), l'**Aide** et **Quitter**.

Le bouton **Ticket** de l'en-tête signale un problème ou propose une idée : le ticket part aux développeurs de FE Maker, sans compte à créer, avec vos captures (et votre projet si vous cochez « Joindre le projet »). Leurs réponses s'affichent sous le ticket. Sans connexion, il reste noté sur votre PC et « Renvoyer » le renvoie plus tard. Un ticket envoyé passe à « Traité » quand les développeurs le ferment ; « Retirer » le range s'il n'a plus lieu d'être (ils en sont prévenus), et vous pouvez répondre à un ticket fermé si le problème revient.

## Limites connues de l'alpha

- Les chapitres ajoutés prennent des places libres du jeu : 21 dans un projet ordinaire, 41 dans un projet vierge.
- Armes et objets ajoutés : copies d'un objet du jeu (49 places) ; une copie de potion ou de bâton garde l'effet d'un objet du jeu, avec ses propres quantités.
- Une épée, une lance ou une hache qui frappe à distance demande une animation qui a le mouvement « Attaque à distance » : la plupart des haches du jeu ne l'ont pas. Le filtre « Frappe à distance » de la bibliothèque en trouve dans le FE-Repo.
- Musique : musiques des chapitres (phases, ouverture, thème de victoire), des combats, thèmes de chef, commande Musique des déroulés et écrans (titre, préparatifs, magasins, game over…), 16 pistes et 12 notes en option (8 pistes sans) , instruments General MIDI (NIMAP2) et batterie complète (option) pour les MIDI faits ailleurs ; pas encore la carte du monde ni d'autres sons que ceux du jeu.
- Carte du monde : on peut seulement la désactiver.
- Compétences : 3 au plus par fiche personnage ou classe ; leurs noms et descriptions sont en anglais dans le jeu.
- Couleurs du portrait : le résultat est approché, à retoucher au besoin ; une animation importée ne protège pas sa monture.
- Pinceaux de terrain : les raccords sont calculés d'après les tuiles du jeu ; les routes sont le point faible, et le terrain autour du trait peut changer un peu.
- « Terminer le jeu ici » ramène à l'écran titre ; le menu propose ensuite de reprendre le dernier chapitre.
- Les copies du dossier `backups/` d'un projet se restaurent à la main.
- Le jeu doit recompiler pour montrer un changement ; il n'y a pas d'aperçu en direct.

## IA et publication

FE Maker est développé en très grande partie avec une IA générative (code, textes, traductions). Le `CREDITS.txt` de votre projet le rappelle : gardez cette mention si vous publiez votre hack. Sur FE Universe, l'art et la musique générés par IA sont interdits et tout usage d'IA dans le code ou les textes doit être déclaré ([règle](https://feuniverse.us/t/ai-policy-updated-2026-10/38008)). Les ressources du FE-Repo sont publiées par la communauté : c'est à vous de vérifier qu'elles respectent cette règle.

Le projet n'est pas affilié à Nintendo ni à Intelligent Systems. Ne partagez jamais de ROM : partagez le patch.
