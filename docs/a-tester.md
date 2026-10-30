# À tester en jeu (alpha, étape 2)

Liste tenue pendant le travail en autonomie du 30/10/2026. Relancer FE Maker avant de tester (interface reconstruite).
Chaque point a déjà été vérifié par un playtest automatique quand c'est indiqué ; il reste ton regard (interface, en jeu).

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
