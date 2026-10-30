# À tester en jeu (alpha, étape 2)

Liste tenue pendant le travail en autonomie du 30/10/2026. Relancer FE Maker avant de tester (interface reconstruite).
Chaque point a déjà été vérifié par un playtest automatique quand c'est indiqué ; il reste ton regard (interface, en jeu).

## Tickets du 30/10 après-midi (58 à 66)

- [ ] #58 Portrait d'un nouveau personnage : sur Bernardo, le panneau de portrait s'ouvre tout seul et propose « Depuis une planche PNG » et « Depuis FE-Repo ». Avant, il affichait seulement « le portrait n° 0 n'existe pas », sans bouton.
- [ ] #59 Portée libre : une arme 1-10 montre ses cases rouges et « Rng 1-10 » (playtest fait : losange complet autour de Seth, écran vu). Toute autre portée marche aussi (2-5, 4-4...). Regarder FluDiBernar : les cases rouges au survol d'« Attaquer » et la fiche. Les bâtons gardent leur portée d'origine.
- [ ] #60 Classe ajoutée : le sprite du modèle s'affiche tout de suite, dans la liste et la fiche, avec « Celui de Pirate tant que vous n'en importez pas un autre ».
- [ ] #61 Animations : la bibliothèque reste ouverte et garde son choix après un import ; cliquer le nom de l'animation importée la rouvre en dessous. Une animation importée depuis le PC n'a pas de source : son nom reste du texte.
- [ ] #62 Bouton « ← Retour » à gauche de « Annuler » (ou Alt + flèche gauche) : revient à l'onglet et à la fiche d'avant. Sur la page Campagne, il ramène aussi au chapitre sélectionné.
- [ ] #63 Sprite Pirate 2 : le carré gris autour du sprite sélectionné venait du fond de la planche FE-Repo. J'ai corrigé les deux images dans ton projet « test » ; les prochains imports sont bons. À revoir en jeu (sélection et marche).
- [ ] #65 Onglet « Options du jeu » : les réglages sont présentés comme le menu Configuration du jeu, dans le même ordre, avec tous ses choix (13 réglages, dont « 2 » pour Animation, Musique, Effets sonores, Couleur des fenêtres). Le point • marque le réglage d'origine. Les noms étaient faux pour Unité et Combat (Panneau / Bulle, Stratégique / Détail) : corrigés.
- [ ] #65 Cases à cocher : alignées avec leur texte partout (règle commune). Si tu en vois une encore décalée, dis-moi où.
- [ ] #66 Projet vierge (écran d'accueil, « Projet vierge » sous le nom) : un chapitre vide « Chapitre 1 » de 15 × 10, sans ennemis ni dialogues, 41 places libres pour tes chapitres, les chapitres du jeu cachés de Chapitres, Cartes, Dialogues et Campagne, sans carte du monde. Case « Retirer aussi les personnages » : il reste un Héros (Eirika renommée, Rapière et Vulnéraire) ; « + Allié » et « + Ennemi » reprennent les places des personnages retirés.
- [ ] #66 En jeu (playtest fait) : le héros bat l'unique ennemi et arrive au chapitre ajouté. **Place au moins un ennemi** : sans ennemi, le chapitre se termine dès la fin du premier tour.
- [ ] #66 Limites : armes, objets et classes sont gardés (les retirer viendra plus tard) ; « Tous les chapitres » dans Dialogues liste encore les messages du jeu ; la liste des personnages garde les entrées sans nom du jeu.
- [ ] Nouveau : « Terminer le jeu ici » sur un chapitre sans sortie (page Campagne) ramène à l'écran titre à la fin du chapitre (playtest fait). Le menu propose ensuite « Reprendre le chapitre » sur ce dernier chapitre : à améliorer.

## Portée sur la carte d'un chapitre

- [ ] Onglet Chapitres : cliquer une unité colore sur la carte où elle peut aller (bleu) et frapper (rouge), selon sa classe, ses armes et le terrain peint. Case « Zone de danger des ennemis » : tout ce que les ennemis peuvent frapper. Les autres unités ne bloquent pas le chemin dans ce calcul. Déplacer l'unité met à jour la zone.

## Titres de chapitre et descriptions

- [ ] Image de titre : les chapitres ajoutés utilisent maintenant les vraies lettres du jeu, lues dans ses images de titre au moment de compiler. Seules G, J, K, N, P, Q, U, X, Y, Z, j, q, x viennent de l'ancienne méthode, le jeu ne les écrivant pas assez dans ses titres ; accents ajoutés sur les minuscules, pas sur les capitales (É reste E). Essai vu sur une planche de comparaison ; à voir en jeu et dans le menu de sauvegarde.
- [ ] Description (touche R) : nouveau champ dans les fiches Personnage, Classe et Objet, avec un avertissement si le texte dépasse deux lignes d'environ 32 caractères (playtest fait : description de Seth avec accents, lue en jeu). Vide pour un personnage ajouté, celle du modèle pour une arme ou une classe ajoutée tant que tu n'y touches pas.

## Hack témoin (étape 3 de l'alpha)

Un test automatique joue un hack de 3 chapitres fait comme dans l'interface : projet vierge, héros renommé, un compagnon réutilisé, deux chapitres ajoutés, un soldat par chapitre, fin du jeu. Il va du premier chapitre au menu de sauvegarde, l'armée suit d'un chapitre à l'autre. Il ne remplace pas ton gel : les cartes y sont vides et il n'y a pas de dialogues.

- [ ] Le faire à la main, avec de vraies cartes et un dialogue par chapitre : c'est l'étape 3 du plan, et ce qui manque pour le gel.

## Nouveaux réglages de confort

- [ ] Onglet « Options du jeu », section Confort : « Barre d'expérience rapide », « Gain de niveau rapide », « Pas d'écran de combat pour les bâtons et les danses ». Playtest fait : le jeu compile et démarre avec les trois. **Leur effet n'a pas été vu en jeu** : soigne une unité avec les animations activées, gagne un niveau sur la carte.

- [ ] « Barres de PV sur la carte » : une petite barre sous chaque unité blessée, rouge sous un tiers de ses PV, verte au-dessus (playtest fait : Seth à 5 PV sur 30). À voir : barres pendant les menus et après un combat, en brouillard de guerre, et si leurs couleurs te vont.

- [ ] « Mode débutant » : une unité vaincue revient au chapitre suivant, soutiens gardés (playtest fait : unité marquée morte, de retour sur la carte suivante). Toujours actif s'il est coché, pas un choix du joueur en début de partie. À voir sur une vraie mort.

## Préparation de l'alpha (rien n'est publié)

- [ ] Écran d'accueil : le panneau « À installer avant de commencer » n'apparaît que s'il manque quelque chose. Pour le voir : quitte Docker Desktop puis recharge la page ; message clair, « Vérifier à nouveau » après l'avoir relancé.
- [ ] Ticket, bouton « Envoyer sur GitHub » : ouvre un signalement pré-rempli dans ton navigateur, rien ne part sans toi. Le dépôt étant privé, seul un compte qui y a accès peut l'ouvrir.
- [ ] `docs/guide.md` et `docs/guide.en.md` : à relire ; c'est ce que liront les testeurs de FEU. `CHANGELOG.md` aussi.
- [ ] Paquet : `python tools/make_release.py` donne `dist/fe-maker-0.1.0-alpha.zip`. Essai fait dans un dossier vide, sur ce PC : installation, décomp téléchargée (18 s), projet vierge, compilation et patch. Pas fait : le lanceur `.bat` lui-même, et un PC sans Python ni Docker.
- [ ] Les workflows GitHub (`image.yml`, `release.yml`) n'ont jamais tourné : ils partiront au premier push. L'image de compilation est à publier avant l'annonce, sinon chaque testeur compile agbcc (une dizaine de minutes).

## Ticket 64 : où sont les conditions et les sauts

Onglet **Dialogues**, choisir un chapitre, puis le bouton ⚙ d'une scène : l'éditeur d'événements s'ouvre. En bas, la liste « Ajouter », groupe « Conditions » :

1. Choisis par exemple « Si un personnage est vivant… » : FE Maker ajoute trois blocs : le test, le saut et l'étiquette.
2. Choisis le personnage dans le premier bloc. Le saut est sélectionné : la commande que tu ajoutes ensuite se place dans la condition, en retrait, avant l'étiquette.
3. Le jeu saute à l'étiquette si la condition est fausse : les commandes en retrait ne s'exécutent que si elle est vraie.

Essai simple : dans l'ouverture du prologue, ajoute « Si un personnage est vivant… » avec Seth, puis un dialogue dans le bloc ; il s'affiche. Refais-le avec un personnage absent du chapitre : il ne s'affiche plus.

## Ouverts sans action de ma part

- #56 musique : en pause, à ta demande. #67 (chapitre d'après une fiche du wiki) : noté dans le cahier pour plus tard. Je les laisse ouverts.

## Chapitres ajoutés (décision 1 : places libres)

- [ ] Page Campagne, fiche d'un chapitre : « + Ajouter un chapitre après celui-ci » (titre, largeur, hauteur ; 21 places libres au départ : étages de la tour et des ruines, chapitres de test). Le nouveau chapitre apparaît dans le graphe juste après, avec son titre.
- [ ] Il a une carte vide (à peindre dans l'onglet Cartes), l'armée du chapitre d'avant en haut à gauche, un groupe d'ennemis vide (onglet Chapitres) et l'objectif « vaincre tous les ennemis » : **placer des ennemis avant de tester**, sinon il est gagné tout de suite.
- [ ] Le chapitre d'avant mène au nouveau, qui mène où allait celui d'avant (playtest fait : chapitre ajouté après le prologue, armée Eirika et Seth, carte 15 × 10, sa fin mène au chapitre 1).
- [ ] Ticket 55 : la fiche d'un chapitre ajouté montre « Ce chapitre mène à » avec le choix du chapitre suivant, et la flèche apparaît dans le graphe (il faut relancer FE Maker).
- [ ] Image du titre : l'écran d'ouverture du chapitre affiche son nom, écrit par FE Maker dans le style du jeu, accents compris (playtest fait : « Le Fort de l'Aube » vu en jeu). À voir aussi dans le menu de sauvegarde.
- [ ] La fiche d'un chapitre ajouté permet de changer son titre ; un titre trop long pour l'image donne un avertissement.

## Musique (première démo)

- [ ] Page Campagne, fiche d'un chapitre, « Musique de la phase du joueur » : « Importer un MIDI », le nom du morceau s'affiche, « Revenir à celle du jeu ».
- [ ] En jeu : le morceau joue pendant la phase du joueur de ce chapitre (playtest fait : le lecteur de musique joue bien le morceau ajouté, mais personne ne l'a écouté).
- [ ] À écouter : le MIDI est joué avec les instruments des musiques de carte du jeu ; selon le fichier, certains instruments peuvent sonner faux ou manquer. Limites : seulement la phase du joueur, pas d'aperçu dans FE Maker, pas encore les morceaux de FE-Repo-Music (ils demandent le jeu d'instruments NIMAP2).

## Corrections des tickets 55 et 57 (à relancer FE Maker)

- [ ] Ticket 55 : un chapitre sans sortie propose « Relier à un chapitre existant » ; un chapitre de l'histoire du jeu n'est plus pris comme place libre. Dans ton projet « test », « Truc » a pris la place du chapitre 1 avant cette correction : le contenu de ce chapitre 1 reste remplacé dans ce projet.
- [ ] Ticket 57 : la carte et le portrait d'origine venaient d'un croisement avec un de mes playtests (même heure, même copie de travail) ; reproduit sans problème sur une copie de ton projet. Une seule compilation à la fois désormais. Options de test rangées dans « Options du jeu ».

## Correction trouvée en route

- [ ] Après un projet avec une animation de combat importée, le build suivant (autre projet, animation retirée) gardait les
  anciennes animations. Corrigé ; vérifié par playtest (un projet non modifié redonne la ROM d'origine).

## Personnages ajoutés

- [ ] Onglet Personnages : les boutons « + Allié » et « + Ennemi » sous la recherche créent « Nouvel allié » / « Nouvel ennemi » en bas de la liste, sélectionné. Annuler (Ctrl+Z) le retire.
- [ ] Le renommer (avec un accent), lui donner une classe, un portrait, des stats ; « Supprimer ce personnage » n'apparaît que pour les personnages ajoutés.
- [ ] Onglet Chapitres : le placer dans un chapitre (allié dans les unités de départ, ennemi en chef) ; il est proposé partout où on choisit un personnage (dialogues, objectif « vaincre le chef », soutiens, conversations « Parler »).
- [ ] En jeu : il est sur la carte avec son nom, son portrait et ses stats (playtest fait : allié et ennemi ajoutés au prologue) ; écran de statut, R sur son nom (description vide pour l'instant).
- [ ] Un allié ajouté qui meurt / survit : écran de fin de chapitre et soutiens (seuls 16 alliés peuvent être ajoutés pour ça).

## Armes ajoutées

- [ ] Onglet Objets, sur une arme du jeu : « + Nouvelle arme d'après celle-ci » crée « <nom> 2 » en bas de la liste (pas proposé pour les fioles, bâtons et objets à usage, dont l'effet est codé par numéro dans le jeu).
- [ ] La fiche d'une arme ajoutée affiche « Arme ajoutée, copie de <modèle> » (cliquable) et « Supprimer cette arme ».
- [ ] La donner à une unité (inventaire d'un chapitre), la mettre dans un coffre, un village ou un magasin.
- [ ] En jeu : nom, icône, stats dans l'inventaire (playtest fait : copie du javelot chez Seth, puissance 11) ; description (R) = celle du modèle pour l'instant.
- [ ] En combat : une copie de hachette se lance comme la hachette (animation de jet), une copie de Feu lance le sort de Feu, une copie de javelot se lance aussi.

## Classes ajoutées

- [ ] Onglet Classes, sur une classe : « + Nouvelle classe d'après celle-ci » crée « <nom> 2 » (même sprite sur la carte, mêmes animations de combat, mêmes promotions), dans la liste principale.
- [ ] La fiche affiche « Classe ajoutée, copie de <modèle> » et « Supprimer cette classe » ; le sprite de la liste et les animations jouées dans la fiche sont ceux du modèle.
- [ ] La donner à un personnage, à une unité générique d'un chapitre ; changer ses stats, ses armes, ses promotions (ou aucune) ; lui importer une animation de combat (FE-Repo ou PC).
- [ ] En jeu : l'unité a le nom de la classe (fiche de statut, R pour la description, celle du modèle pour l'instant), se déplace avec le sprite du modèle (playtest fait : Seth en copie de Paladin se déplace), combat avec ses animations.
- [ ] Promotion : un personnage d'une classe ajoutée avec un objet de promotion promeut vers les classes choisies ; sans promotion choisie, l'objet ne s'utilise pas.

## Conditions et sauts dans les événements

- [ ] Éditeur d'événements, liste « Ajouter » : un groupe « Conditions » (« Si un personnage est vivant… », « Si un drapeau est levé… », « Si le tour est au moins… ») et les commandes de test, mémoire, étiquette, saut et appel.
- [ ] Ajouter « Si un personnage est vivant… » : test + saut + étiquette ; le saut est sélectionné, la commande ajoutée ensuite se place dans le bloc, en retrait.
- [ ] Les scripts du jeu s'affichent avec ces formulaires (plus de blocs « tel quel » pour BEQ, LABEL, CALL…) et en retrait dans leurs conditions ; « → bloc n » mène à l'étiquette, « étiquette absente » si elle manque.
- [ ] En jeu : un dialogue qui ne s'affiche que si un personnage est vivant (playtest fait : le prologue démarre avec une condition ajoutée à son ouverture ; le comportement de la condition reste à voir).

## Sprites de carte

- [ ] Fiche d'une classe, panneau « Sprite sur la carte » : le sprite dans les trois couleurs (joueur, ennemi, allié), « Celui du jeu ».
- [ ] « Bibliothèque FE-Repo » : recherche par nom (le nom de la classe est proposé), dossiers, auteurs et licence ; « sans animation de marche » quand FE-Repo n'a que l'image immobile ; « Utiliser » importe le sprite.
- [ ] « Importer depuis le PC » : choisir une image immobile (16 × 48, 16 × 96 ou 32 × 96) et, si on l'a, la marche (32 × 480) ; une mauvaise taille donne un message clair.
- [ ] Le nouveau sprite apparaît dans la liste des classes, dans les trois couleurs, et sur les cartes des chapitres ; les auteurs FE-Repo sont dans CREDITS.txt du projet ; « Revenir à celui du jeu ».
- [ ] En jeu : les unités de la classe ont le sprite importé, immobiles et en marche (playtest fait : la classe Paladin avec les images de l'archer, Seth immobile et en marche) ; un sprite 16 × 32 (cavalier) ou 32 × 32 (monstre).

## Options du jeu

- [ ] Nouvel onglet « Options du jeu » : réglages d'une nouvelle partie (animations, vitesse du texte et du jeu, curseur, fin de tour, fenêtres, prévisions), la valeur du jeu d'origine indiquée dans chaque liste.
- [ ] Section « Confort » : « Pas de zone de déplacement pour les unités immobiles » (playtest fait : O'Neill, chef du prologue, ne montre que sa portée d'attaque), « Passer l'ouverture », « Titre de chapitre rapide », « A maintenu accélère les déplacements ».
- [ ] En jeu, avec « Démarrage normal » dans les options de test : le jeu démarre sur le menu de sauvegarde ; nouvelle partie : menu Options avec les réglages choisis (playtest fait : texte rapide et curseur coupé lus dans la mémoire) ; titre de chapitre passable tout de suite ; A maintenu accélère.
- [ ] Le patch exporté (.ups) garde ces options.
