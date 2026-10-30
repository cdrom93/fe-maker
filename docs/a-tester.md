# À tester avant le gel de l'alpha

Relancer FE Maker avant de tester. Les cases se cochent sur https://claude.ai/artifact/GcH46bW4mcrDoGaEMZj8Hb. Un point « playtest fait » a déjà tourné en automatique : il reste ton regard.
## Pinceaux de terrain

- [ ] Onglet Chapitres, vue Carte, panneau « Terrains » : choisis Rivière, Route ou Montagne et peins au crayon. À la fin du trait, les tuiles se raccordent toutes seules, comme sur les cartes du jeu, et un Annuler retire tout le trait. Peindre de la Plaine efface proprement. Marche aussi avec Rectangle et Remplir.
- [ ] Solveur refait : autour du trait, le terrain voisin peut changer pour que tout se raccorde (une pente autour d'un pic, une côte le long de la mer). À vérifier à l'œil. Limite connue : les routes, que le jeu dessine souvent en plaine.

## Tickets 77 et 78

- [ ] #77 Menu Configuration du jeu : la ligne « Staff & Dance » est juste sous « Animation » (2e ligne), son aide tient sur la ligne (« Animate staves and dances ») et la dernière ligne, « Window Color », s'affiche en entier. Recompile pour le voir.
- [ ] #78 Page Campagne : un chapitre qui se termine sur « Terminer le jeu ici » mène à une case « Fin du jeu » dans le graphe.

## Scripts plus simples (ticket 70)

- [ ] Dialogues, ⚙ d'une scène : la scène se lit maintenant étape par étape (« Dialogue », « Selon : ... », « Faire venir un groupe : ... »), les commandes techniques cachées. Cliquer une étape montre ses commandes ; « Modifier le texte » ouvre la conversation ; ✕ retire l'étape (pour une condition, seul le test part, ce qu'elle contenait reste). « Vue détaillée » rend l'ancienne vue, et le choix est retenu.
- [ ] Liste de gauche : les scènes sans dialogue sont cachées, sauf ouverture, fin et scènes que tu as changées. Case « Afficher les scènes sans dialogue ».
- [ ] Dis-moi si c'est assez simple : je n'ai pas touché au fonctionnement des événements, seulement à leur présentation.

## Interface simplifiée et déroulé du travail

- [ ] Les avertissements ne sont plus en haut : ils restent dans « À faire » de la page Campagne. Les erreurs, qui bloquent le test, restent en haut.

## À faire sur les chapitres

- [ ] Page Campagne, « À faire » : un chapitre ajouté ou vierge sans ennemi, ou qui ne mène nulle part, est signalé avec son nom. Cliquer le nom ouvre le chapitre.
- [ ] « À faire » ne montre plus les avertissements sur ce que le jeu d'origine fait déjà (noms de balistes trop longs...) : seulement ce que ton projet a changé.

## Hack témoin (étape 3 de l'alpha)

Un test automatique joue un hack de 3 chapitres fait comme dans l'interface : projet vierge, héros renommé, un compagnon réutilisé, deux chapitres ajoutés, un soldat par chapitre, fin du jeu. Il va du premier chapitre au menu de sauvegarde, l'armée suit d'un chapitre à l'autre. Il ne remplace pas ton gel : les cartes y sont vides et il n'y a pas de dialogues.

- [ ] Le faire à la main, avec de vraies cartes et un dialogue par chapitre : c'est l'étape 3 du plan, et ce qui manque pour le gel.

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

## Musique (première démo)

- [ ] Page Campagne, fiche d'un chapitre, « Musique de la phase du joueur » : « Importer un MIDI », le nom du morceau s'affiche, « Revenir à celle du jeu ».
- [ ] En jeu : le morceau joue pendant la phase du joueur de ce chapitre (playtest fait : le lecteur de musique joue bien le morceau ajouté, mais personne ne l'a écouté).
- [ ] À écouter : le MIDI est joué avec les instruments des musiques de carte du jeu ; selon le fichier, certains instruments peuvent sonner faux ou manquer. Limites : seulement la phase du joueur, pas d'aperçu dans FE Maker, pas encore les morceaux de FE-Repo-Music (ils demandent le jeu d'instruments NIMAP2).

## Conditions et sauts dans les événements

- [ ] Éditeur d'événements, liste « Ajouter » : un groupe « Conditions » (« Si un personnage est vivant… », « Si un drapeau est levé… », « Si le tour est au moins… ») et les commandes de test, mémoire, étiquette, saut et appel.
- [ ] Ajouter « Si un personnage est vivant… » : test + saut + étiquette ; le saut est sélectionné, la commande ajoutée ensuite se place dans le bloc, en retrait.
- [ ] Les scripts du jeu s'affichent avec ces formulaires (plus de blocs « tel quel » pour BEQ, LABEL, CALL…) et en retrait dans leurs conditions ; « → bloc n » mène à l'étiquette, « étiquette absente » si elle manque.
- [ ] En jeu : un dialogue qui ne s'affiche que si un personnage est vivant (playtest fait : le prologue démarre avec une condition ajoutée à son ouverture ; le comportement de la condition reste à voir).

## Options du jeu

- [ ] Le patch exporté (.ups) garde ces options.
