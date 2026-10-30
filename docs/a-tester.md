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
