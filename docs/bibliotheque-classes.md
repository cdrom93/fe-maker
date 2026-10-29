# Bibliothèque de classes avec leurs animations (ticket 44, étude du 29/10/2026)

Demande de l'utilisateur : « bibliothèque de classe avec les animations etc ». Idée : choisir une classe dans une
bibliothèque (celles du jeu et celles de la communauté), la voir avec son animation de combat et son sprite de carte,
et l'ajouter au projet d'un clic.

## Ce qui existe déjà

- **Dans le jeu** : environ 120 classes, chacune avec une animation de combat par type d'arme (table des animations,
  `battle_animations` de la décomp), un sprite de carte immobile et un en mouvement. FE Maker sait déjà afficher les
  sprites de carte et éditer les classes (onglet Classes), mais pas montrer les animations de combat.
- **Dans le FE-Repo** (déjà parcouru par FE Maker pour les portraits, `ferepo.py`) : 2 024 dossiers d'animations de combat
  (« Battle Animations »), plus « Map Sprites » et « Class Cards ». Chaque animation est un dossier au format de
  FEBuilder : un script `.txt` (images, durées, sons, moments du coup) et ses images `.png` (16 couleurs). Crédits dans
  le nom du dossier, comme pour les portraits.
- **FEBuilderGBA** (GPL-3.0, autorisé) sait importer ce format (c'est son format) : son code sert de référence.

## Ce qu'il faudrait faire

1. **Voir les animations du jeu** : lire les animations de la décomp (images compressées, découpage en sprites,
   déroulé des images) et les jouer dans la fiche de classe. Moyen (lecture seule, pas de risque pour la ROM).
   Alternative plus rapide : capturer les animations dans le jeu avec le playtest sans fenêtre (un combat par classe,
   images enregistrées une fois pour toutes) ; moins propre, mais pas de décodeur à écrire.
2. **Bibliothèque FE-Repo** : parcourir les animations comme les portraits (vignettes, recherche, auteurs), avec un
   aperçu de la première image.
3. **Importer une animation** : convertir le script FEBuilder et ses images vers les fichiers de la décomp
   (images, découpage en sprites, script de l'animation, palette), l'ajouter à la table des animations et la relier à
   une classe et un type d'arme. C'est le gros morceau (format d'animation du moteur à écrire, limites de taille des
   images à contrôler).
4. **Nouvelle classe complète** : une classe ajoutée au projet (copie d'une classe existante), avec l'animation, le
   sprite de carte (FE-Repo « Map Sprites ») et la carte de classe importés. Les nouvelles classes demandent aussi
   d'agrandir les tables du jeu (classes, sprites de carte) : à vérifier dans la décomp.

## Proposition

Commencer par 1 (voir les animations du jeu dans l'onglet Classes) et 2 (parcourir le FE-Repo), qui ne touchent pas à la
ROM. Puis 3 et 4, après l'accord de l'utilisateur : c'est un chantier comparable à l'import de portraits, en plus gros.
