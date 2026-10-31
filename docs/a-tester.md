# À tester avant le gel de l'alpha

Relancer FE Maker avant de tester. Les cases se cochent sur https://claude.ai/artifact/GcH46bW4mcrDoGaEMZj8Hb. Un point « playtest fait » a déjà tourné en automatique : il reste ton regard.
## Pinceaux de terrain

- [ ] Onglet Chapitres, vue Carte, panneau « Terrains » : choisis Rivière, Route ou Montagne et peins au crayon. À la fin du trait, les tuiles se raccordent toutes seules, comme sur les cartes du jeu, et un Annuler retire tout le trait. Peindre de la Plaine efface proprement. Marche aussi avec Rectangle et Remplir.
- [ ] Solveur refait : autour du trait, le terrain voisin peut changer pour que tout se raccorde (une pente autour d'un pic, une côte le long de la mer). À vérifier à l'œil. Limite connue : les routes, que le jeu dessine souvent en plaine.

## Tickets 82 à 99

- [ ] #94 Dialogues : un portrait porté par un de tes personnages affiche son nom (Lorn, Mira), dans le choix des portraits comme dans le dialogue.
- [ ] #95 Objets de la carte, village ou maison : « Autre personnage… » fait parler n'importe quel portrait, tes personnages en tête.
- [ ] #90 Onglets Chapitres et Campagne : un clic sur le titre du chapitre, en haut de sa fiche, le renomme (Entrée pour garder, Échap pour annuler).
- [ ] #91 Palette de carte : quatre parties, Terrains, Bâtiments, Décors, Toutes les tuiles. Les maisons, forts, arènes sont là même sur une seule case ; coffres et ponts dans Décors, selon le jeu de tuiles. Tourner une tuile est replié tout en bas.
- [ ] #93 Onglet Dialogues : un ✕ supprime une scène du jeu (tour, « Parler », village, scène appelée) ; elle se rétablit depuis « Scènes supprimées ». L'ouverture et la fin du chapitre restent. Les scènes appelées vides d'un chapitre vidé ne s'affichent plus.
- [ ] #85 Personnages : la liste montre les alliés, puis les ennemis.
- [ ] #86 Bibliothèque d'animations : un clic sur le nom d'une arme montre l'aperçu de cette arme.
- [ ] #87 #88 Projet vierge : plus de message sur l'Iron Sword, ni sur aucune unité du jeu que tu n'utilises pas.
- [ ] #89 Projet vierge : seuls ton héros et tes personnages restent dans la liste principale (les génériques sont repliés dessous). Ton projet en cours est nettoyé à sa prochaine ouverture.
- [ ] #82 Onglet Chapitres : l'objectif est en haut, sous le titre du chapitre, avec le convoi et le brouillard.
- [ ] #83 Projet vierge : plus d'avertissement sur les unités des chapitres du jeu que ton projet n'utilise pas.
- [ ] #84 Nouveau personnage : le portrait importé s'affiche tout de suite, sans rafraîchir la page.
- [ ] #96 Une description avec des accents (« Le héro de ce hack de test ! ») s'affiche sans lettres en trop en jeu. Vaut aussi pour les dialogues et les objectifs.
- [ ] #97 La description d'une classe modifiée apparaît en jeu.
- [ ] Répondre à un ticket ouvert pour le compléter, avec du texte et des captures (bouton « Répondre » dans la liste, panneau Tickets).
- [ ] #99 Options du jeu, « Zone de danger avec Select » : Select montre la portée des ennemis, Select ou B revient à la carte, A passe aux portées de bâton si des ennemis en ont.

## Tickets 70, 79 et 80

- [ ] #70 Vocabulaire : partout, une scène a un déclencheur, un déroulé (l'ancien « script ») et des dialogues. Le mot « conversation » a disparu, la vue en bulles s'appelle « Bulles ». Dis-moi s'il reste un mot qui te gêne.
- [ ] #70 Onglet Dialogues, liste des scènes : les scènes de tour et « Parler » du jeu s'écrivent en phrase modifiable : « Début du tour [3] [joueur] », « [Seth] parle à [Franz] ». Change un mot, recompile, et vérifie en jeu que la scène suit.
- [ ] #79 #80 Onglet Chapitres, à droite des trois vues : « + Ajouter un chapitre » ; dans la vue Carte : « + Nouvelle carte », qui crée un chapitre avec sa carte vide, puisque chaque chapitre a la sienne. Le nouveau chapitre s'ouvre tout de suite.

## Ticket 81

- [ ] #81 Une classe qui n'est pas Danseuse peut danser (ta Prêtresse Healot) sans brouiller l'écran. Elle n'a pas d'animation de danse sur la carte, faute de sprite prévu : seuls le son et l'effet jouent. Le jeu d'origine plantait aussi (écran noir). Recompile pour le voir.

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

## Le hack d'essai : « La Fuite de Lorn » (gel de l'alpha)

Trois chapitres à faire toi-même, de bout en bout, pour toucher à presque tout. Compte une à deux heures. Note ce qui coince avec le bouton Ticket : c'est le but.

- [ ] Préparation : nouveau projet, « Projet vierge », case « Retirer aussi les personnages ». Héros « Lorn » (nom, stats, description avec la touche R).
- [ ] Options du jeu : coche les barres de PV, un réglage de confort au choix, et « Staff & Dance ».
- [ ] Personnages : « + Allié » Mira, une soigneuse, avec un portrait et un bâton ; « + Allié » Bran ; « + Ennemi » Vorgan, le chef.
- [ ] Classe : « + Nouvelle classe » d'après le Chevalier, « Garde », pour Bran, avec un sprite de carte et une animation de combat de FE-Repo.
- [ ] Arme : « + Nouvelle arme » d'après un javelot, « Lance longue », portée 1-3, réservée à Vorgan.
- [ ] Chapitre 1, « Le Village », 15 × 10 : carte au panneau Terrains (rivière, forêt, montagne), un village en bâtiment entier et un coffre. Objectif « Vaincre tous les ennemis », trois ou quatre ennemis.
- [ ] Chapitre 1, dialogues : un dialogue d'ouverture en bulles, un dialogue de fin, et ce que donne le village.
- [ ] Teste le chapitre 1 avec « ▶ Tester ce chapitre ». Regarde la zone de danger avant de placer tes unités.
- [ ] Chapitre 2, « Le Pont », avec « + Ajouter un chapitre » : objectif « S'emparer d'une case » sur une porte de château, un coffre derrière une porte.
- [ ] Chapitre 2, combat : Vorgan en chef, avec la Lance longue et sa réplique de combat. Ses dernières paroles, puis des « Renforts » au tour 3.
- [ ] Chapitre 2, scènes : une scène de tour écrite au tour 2, puis change son tour dans la phrase. Un dialogue « Parler » qui recrute un allié vert.
- [ ] Soutien : « Nouveau soutien » entre Lorn et Mira, avec son dialogue C.
- [ ] Chapitre 3, « La Fuite » : objectif « Survivre » 6 tours, une armurerie et un magasin. Pour la fin du chapitre, un déroulé avec une condition « Si un personnage est vivant… » sur Mira.
- [ ] Campagne : « Terminer le jeu ici » sur le chapitre 3, renomme un chapitre, vérifie la liste « À faire ».
- [ ] Joue tout d'un coup avec « ▶ Tester depuis le début » : l'armée doit suivre d'un chapitre à l'autre, et les soutiens aussi.
- [ ] Menu Projet, « Exporter le patch », puis applique le `.ups` sur une ROM propre et lance-la dans mGBA.

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
