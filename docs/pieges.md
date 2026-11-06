# Pièges déjà rencontrés

Sortis de CLAUDE.md le 30/10/2026 pour ne pas les charger à chaque session. **Lire la section du thème
avant d'y toucher** (`grep -n '^## ' docs/pieges.md`). Écrits en anglais comme le code ; ajouter un nouveau
piège dans sa section.

## Build et décomp

- The decomp checkout must use LF line endings (`core.autocrlf=false`, `core.eol=lf`), or the Linux build breaks.
- Text compression packs 2 bytes per symbol: a text that ends on a byte alone is read past its end (`pad_text`, used by names, dialogues, objectives, descriptions). 0x23 `#`, 0x7F, 0xE9 `é` at the start of a pair and bytes below 0x20 are packed alone: counting characters is not enough.
- C code FE Maker writes into the decomp: no `static const` tables in a function of a file whose `.rodata` the link script discards (`bmcontainer.o`, others): the link fails with "defined in discarded section `.rodata`". Write comparisons; compile with `tests/local` before telling the user it works.
- Docker fails to start when CPU virtualization is off in the BIOS (happened several times on the user's PC).
- C-SkillSys prototype (ticket 27, stopped 24/10/2026, removed from the repo 29/10/2026, still in git history): it rebuilt every game text from its own copy and replaced item/spell tables, so it would erase FE Maker's edits: see `docs/separation-force-magie.md` before going further. Builds also output `fireemblem8.elf`.

- `data/banim/data_banim.o` dépend des objets que liste `linker_script_banim.txt`, pas du script lui-même : après un projet avec une animation importée, le build suivant (autre projet, animation retirée) gardait les anciennes animations, et un projet non modifié ne redonnait plus la ROM d'origine. `docker/entrypoint.sh` efface l'objet quand le script change (30/10/2026).
- Fiche d'unité, page 1 : la ligne combats / victoires / défaites (`DisplayBwl`, ligne 14) n'apparaît qu'après une première partie finie ; une ligne de plus dans la colonne de gauche (Mag, 06/11) la recouvrait sans que les tests sans fenêtre le voient. `heredoc` du terminal : il abîme les antislashs (`
` du code C) ; écrire ces scripts dans un fichier.
- Un remplacement de texte dans la décomp prend la première occurrence : `gStatScreen.inTransition = FALSE;` est d'abord dans `PageSlide_OnEnd`, pas dans `StartStatScreen` (#166, 06/11 : le réglage se remettait à zéro à chaque page) ; choisir une ancre unique (vérifier avec `grep -c`).
- Redessiner un texte du jeu dans une autre couleur : `PutDrawText` n'efface pas le `Text`, les pixels du nouveau texte se mêlent (OU binaire) à ceux de l'ancien et donnent des teintes fausses (souvent le contour). Appeler `ClearText` avant (ticket 166, noms des stats colorés).

## Données du jeu (personnages, classes, objets, textes)

- Bâtons et objets agissent par leur numéro dans le moteur (`switch (GetItemIndex(item))`, `== ITEM_X`, tables de l'IA `{ ITEM_X, fonction }`) : une copie n'agit que si elle est ajoutée à ces tests (`_copy_item_behaviour`). Un numéro écrit en dur dans `asm/` ne serait pas suivi.
- Images en gris de gbagfx (tuiles sans palette) : le blanc est la couleur 0 (couleur = 15 − gris / 17), et passer de L à P avec Pillow remappe les index : utiliser `Image.frombytes("P", ...)`.
- A unit with any magic rank plays its battle animation's magic (ranged) moves, whatever weapon it strikes with (`UnitHasMagicRank` in `banim-battleparse.c`): a mage with a sword stood still. Projects mixing magic and physical ranks get `tweaks.animation_modes_by_weapon` (docs/audit-decomp.md item 59).
- `decomp.animated_weapons` is shared by every project: merge the project's animations into a copy (`validation.animated_weapons`), never into it (ticket 50).
- Unit definitions set each unit's class in every chapter: a character class change must retarget unit defs. The character sheet is the only source of a named character's class: chapter edits never write `classIndex` for `CHARACTER_` units (class 0 = the character's class when a unit switches to a named character); only generic units (raw ids 0x80...) get a class per chapter.
- Weapon ranks a class cannot animate crash the battle animation (validation `noBattleAnimation`).
- Weapon locks: generic CA/IA_LOCK 1,2,4,5,6,7 are allocated automatically from items' `reservedFor`; LOCK_3 means monster weapon.
- Several chapters share an internal id: key chapters by index.
- An item reservation equal to the original one is never rewritten (the original Mani Katti is reserved for nobody; an edited empty reservation means unrestricted).
- The game takes the first matching entry of its quote tables (`GetBattleQuoteEntry`, `GetDefeatTalkEntry`): a new entry must go before the game's entries it would lose to (`quotes._battle_position`). Supports: the "Support" command appears only when the points sit exactly at 80 / 160 / 240; a pair starting at 81+ skips its C conversation (`supports.skipped_levels`).
- Text byte counts (padding to even runs) use `texts.text_size`: an accented letter is one byte in the game, not its UTF-8 length.
- `assets.portrait_names` (and other readers) are `lru_cache`d: copy the list before adding to it (`list(...)`), or every later call sees the additions.
- `validation.weapon_problem` mirrors `CanUnitUseWeapon`; unusable weapons are reported only when the project changed something (`_validate_unit_weapons`), on the edited unit or once on the changed sheet.
- A character's own battle palette (`gAnimCharaPalConfig`, Seth as a Paladin) is drawn over whatever animation his class plays: imported animations skip it (`banim_import.without_unique_palettes`, in `banim-ekrmain.c`). Battle animation playtests: the right side's animation index is `gBanimIdx` + 2 (16 bits); Seth attacks with his first weapon, a sword.

- Menu Configuration du jeu : les lignes commencent à la rangée 5 du tilemap, deux rangées chacune, et les rangées bouclent à 32 : une 14e ligne perdrait sa moitié basse. FE Maker les décale d'une rangée (ticket 77). Une 15e ligne demanderait de revoir le dessin.

- Danser sur la carte demande une 6e animation au sprite de marche, que seuls les sprites de danseuse ont : donner « Danse » à une autre classe brouille l'écran dans le jeu d'origine aussi, animations coupées ou non (`danceanim.py`).
- Planches FE-Repo indexées : le fond n'est pas toujours la couleur 0 (carré gris autour du sprite sélectionné) : prendre la transparence du PNG, sinon le pixel en haut à gauche.

- Une arme de contact à portée 2 frappe de loin seulement si l'animation de la classe appelle le sort dans son mode à distance (`banim.casts_at_range`) : les haches ordinaires ne le font pas, d'où l'avertissement `noRangedAnimation`.

- **Rangs d'armes et montée automatique** : une unité en montée automatique reçoit, pour chaque arme ou bâton qu'elle ne peut pas utiliser, le rang exact que l'objet demande, si elle a déjà un rang dans ce type (`UnitAutolevelWExp`, src/bmunit.c). Ne pas avertir d'un rang trop bas dans ce cas (ticket 157). La portée « Mag/2 » d'un bâton vaut au moins 5 (`GetUnitMagBy2Range`).

## Cartes

- Les tuiles de sprites 0x12-0x7F des premières lignes sont aux particules de la météo : les barres de PV et les bulles sont en 0x340-0x37F, libres pendant la carte (#142). Le prologue cache les icônes de la carte (`EVFLAG_HIDE_BLINKING_ICON`) : tester les barres sur un autre chapitre.
- Pendant une animation de combat, le combattant de droite a son image en tuiles de sprites 0x300-0x3FF, et la boîte d'une réplique de combat recharge les graphismes d'interface (`Talk_OnInit` → `LoadObjUIGfx`) : ce qu'on y ajoute ne doit rien écrire tant que `IsBattleDeamonActive()` (#161, taches sous l'adversaire).
- Pinceaux de terrain : les paires de tuiles vues sur les 18 cartes d'un jeu de tuiles sont trop rares pour raccorder quoi que ce soit (2 à 7 voisines par tuile, aucune tuile de mer ne touche l'herbe la plus courante) : `autotile.py` compare aussi les matières des bords, lues dans les pixels. Le type de terrain ne dit pas tout : beaucoup de routes du jeu sont en terrain plaine.

- Map tileset PNGs are inverted grayscale (index = 15 − v/17); map palettes: 5 normal then 5 fog palettes.
- Map layouts are keyed by layout id (file stem): several chapters can share one, so painting it changes all of them (the UI says so). Map change sets are keyed by layout id too (one per layout).
- Map checks against units (`_validate_chapter_maps`) only report what the project changed: the original game has units outside their map and under roofs removed by map changes.
- Map tile edits proposed by a mirror/turn are not saved until the user creates them (`pendingTiles` in `MapEditor.svelte`); removing an added metatile also drops the 8x8 tiles only it used (`ui/src/lib/tileEdits.ts`).
- Une carte décalée à gauche ou en haut garde les coordonnées écrites dans ses scènes : l'ouverture du chapitre 2 bloque alors le jeu avant le tour 1 (`MOVE` et `SVAL(EVT_SLOT_B, 0x5000c)` visent les anciennes cases). Les événements de lieu suivent (`offsets`, `mapobjects.move_location_events`), sauf `Seize`, réécrit par l'objectif.
- A broken snag or wall, an opened door or chest, a visited village apply the change holding the object's own cell (`GetMapChangeIdAt`): a manual change moved off that cell never shows (validation `manualChangeOffObject`).
- Map objects: only objects that are new on the painted map get automatic changes and events; original objects keep their original behavior (some are decoration without event) unless the project sets them. A change only counts for an object if it puts it in its used state (`USED_TERRAIN`): a village painted inside a brigand-ruin rectangle would else ruin the wrong village.
- The user's server may be older than `ui/dist` (it serves the rebuilt UI until they restart it): UI code reading a new API field must fall back to the old answer. Ticket 22's "used tiles" check read `originalTileset`, which the old server did not send, so every added tile looked unused and a used one got removed. Map cells on a removed added tile are now a validation warning (`missingTile`).
- A village is destroyed through the change holding its roof (one cell above the gate), and the engine keeps the last change holding a cell: new villages get a ruined-village change written before all the other changes (`mapobjects.ruin_change`, `obj["ruin"]`), so the gate's last change stays the closed village. Playtests that end the turn must open the map menu on an empty cell (`game.units()` positions), and an enemy boss dying on a counter ends the prologue before other enemies act.

## Événements et enchaînement des chapitres
- Une teinte d'écran (`EvtColorFadeSetup`) ne dure que le temps de la scène, et un playtest qui passe la scène avec Start ne la voit jamais : avancer avec A pour la vérifier.

- Drapeaux temporaires : le jeu n'efface à chaque chapitre, et une sauvegarde rapide ne garde, que les 40 premiers (5 octets). Au-delà, un numéro repris d'un chapitre à l'autre reste levé et l'événement ne se déclenche plus (ticket 112 : porte au même numéro qu'un village). `chapterflags.py` efface les 16 octets et en sauvegarde 7 dès qu'un drapeau dépasse 40.

- `objectives.clear_events` vide les listes d'un chapitre : ce qui ajoute un événement (renforts) doit passer après (ticket 109). Les groupes de tour du jeu n'ont plus d'événement dans un chapitre vidé : `_apply_group_turns` en remet un à ceux que le projet a remplis.

- Chemin d'entrée impossible (REDA, ticket 108) : si une unité ne peut pas atteindre sa destination, `GenerateBestMovementScript` écrit des pas sans fin et écrase l'EWRAM (procs compris), plantage quelques secondes plus tard. Une unité déplacée perd donc son chemin, et les groupes d'une carte repeinte apparaissent à leur place (`DecompData.apply_maps`). Une commande MOVE d'un déroulé vers une case impossible a le même défaut.

- Opening scenes often load units on other maps (cutscenes): `chapter_unit_groups` marks groups loaded before the last `LOMA` as "cutscene"; editing them does not change the battle.
- Test builds' simplified prologue skips the scene that gives Eirika the Rapier: she has no weapon unless the project gives her one (story-tied, left as is; told the user 24/10/2026).
- Changing where a chapter leads works in game (playtest); the prologue sent straight to chapter 2 showed its title, then stayed black (24/10/2026): the game took chapter 2 for a skirmish (ticket 39, see the world map pitfall below and docs/audit-decomp.md item 57); fixed when the project goes without the world map.
- Event scripts can use messages made by the project: quotes of kind "scene" with a "key", referenced as "new:<key>" (`dialogues.SCENE_MESSAGE`); `apply_dialogues` adds them and rewrites the arguments. A rewritten opening scene must bring the army back with `LOAD2` on the chapter's players group (`ScriptEditor.simpleScene`).
- MNCH / MoveToChapter go to the chapter of the lord's world map node, not to their argument: test builds started on the map, and projects with the "world map" option off (`Project.world_map`, `fe-maker.json` "worldMap", exported patch too, ticket 39), redefine MNCH as MNC2 (`tweaks.without_world_map`). The original story's MNCH arguments are often stopover chapters (chapter 1 -> Castle Frelia, 56). Without the world map, `GetBattleMapKind` must return STORY too: it takes any chapter from 2 on whose world map place was never reached for a skirmish and runs the skirmish opening (black screen, ticket 39). To debug a stuck playtest, list the live procs and the event engine's current command (sProcArray at the start of proc.o's EWRAM, 0x6C per proc). The "Story flow" tab is now the "Campaign" page (`ChapterFlow.svelte`, tab id still `flow`). A character's new portrait follows them in dialogues (`DecompData._follow_portraits`, and `/api/dialogues/faces` for the preview).

- Les fichiers d'événements d'un chapitre ne partagent pas toujours un préfixe : les étages de la tour ont `tower1-eventinfo.h` et `tower-eventscript.h`. Ne pas trouver un script par le préfixe seul (ticket 55 : la scène de fin d'un chapitre ajouté, absente de la page Campagne, jouait pourtant en jeu).

- L'introduction d'une nouvelle partie a deux morceaux : `StartIntroMonologue` (sous-titres) et, surtout, le récit sur Magvel, qui est l'événement de carte du monde `EventScrWM_Prologue_Beginning` : il tourne même sans carte du monde (ticket 115). Une option « compilée seulement » n'est pas vérifiée : jouer une vraie nouvelle partie.

## Tests en jeu (playtest)

- Dans le prologue du jeu, le menu d'une unité change selon ses voisins (Seth peut porter Eirika : « Porter » passe avant « Objet ») et les ennemis attaquent. Pour tester une action, utiliser le banc d'essai `_bench` de `tests/local/test_playtest.py` : projet vierge, unités seules sur une plaine, un ennemi sans arme au loin (ou à côté, `enemy_at`), menu toujours « Objet, Attendre ». Une unité seule qui a agi finit le tour d'elle-même, et l'ennemi bouge pendant sa phase : garder une seconde unité inactive. L'héroïne du projet vierge n'a pas le rang D (pas d'Épée d'acier). Après « Interrompre », la mémoire garde unités et tour : un test de reprise qui ne les efface pas passe sans rien prouver (`_bench_suspend_and_resume` les efface avant « Reprendre le chapitre »). Le chapitre vierge du banc n'affiche pas les icônes des unités (barres de PV, bulles) : les tester sur le prologue.
- In playtests, wait for animations before reading the screen (`press` waits 20 frames; a move takes ~40), pick menu entries by their position (menus differ with the situation: Attack only when an enemy is in range), and remember Canto (Seth can move again after an action).
- Playtest harness: a chapter's turn/phase say "player" while its opening scene still runs; tapping A after it selects units. Wait for the scene to end before acting (`tests/local/test_playtest.py` shows how).

- Deux compilations en même temps partagent la copie de travail du volume Docker : « Build failed » sans erreur du compilateur, ou pire, une ROM qui marche en mélangeant les fichiers de deux projets (ticket 57 : carte et portrait d'origine dans le projet de l'utilisateur, pendant un de mes playtests). `builder.build_lock` les fait attendre, entre tous les programmes.

## Outils et interface

- `pytest ... | tail` rend le code de sortie de `tail` : un test rouge n'arrête pas un `&&`. Mettre `set -o pipefail` avant de chaîner un commit. Un test qui crée un projet passe `decomp_dir=decomp_dir` : sinon il lit la décomp installée sur la machine, absente de la CI.

- **Un champ ajouté (`FIELDS_ADDED_LATER`)** : ce qu'un projet a ajouté (arme `ITEM_NEW_`, classe) le prend chez son modèle, sinon la fiche plante. Chaque `Project.load` qui complète relit toute la décomp : les champs sont donc enregistrés dès la première lecture, et `validate` ne charge qu'une fois (90 s sur « La Fuite de Lorn » avant, page vide en attendant). Essayer un nouveau champ sur une copie d'un vrai projet, pas seulement sur un projet neuf.

- Bash heredocs passed through the tool break on some quote/backslash mixes ("unexpected EOF") and can mangle `\b`, `\n` or `\x00` in Python sources (real newlines, NUL bytes): write patch scripts with the Write tool and edit regex code with the Edit tool.
- PowerShell eats backticks in inline scripts: edit files with the Edit tool or Python, not PowerShell strings.
- Editors loaded asynchronously (chapters, maps) must read `nav.focus` once their list is loaded: `followFocus` alone misses a link that mounted the tab.
- Show validation problems with `problemText(p)` (`ui/src/lib/i18n.svelte.ts`), not `t('problem.' + code)`: it turns `terrain`, `object` and `wtype` parameters into names.
- Svelte `$derived` lists already hold a record right after `list.update` adds it: take its index before saving ("Add a change" opened nothing because of this).
- Svelte 5 : une prop `x={a.b}` n'est pas mémorisée : un `$effect` qui lit `x` repart dès que `a` change, même si `a.b` est identique (la bibliothèque d'animations se vidait). Passer par `$derived(x)`.
- Un `<img>` masqué par `onerror` le reste quand sa source change : une classe ajoutée demande son sprite avant d'être enregistrée ; utiliser l'id du modèle.
- `FE_MAKER_HOME` ne déplace pas le dossier des projets : `POST /api/projects` crée dans le vrai `FE Maker Projects` de l'utilisateur. En test, passer un chemin explicite, ou ouvrir un projet du dossier de test.
- Une option du jeu retirée (fonction annulée) peut rester dans le `fe-maker.json` d'un projet : l'interface renvoie toutes les options à chaque case cochée, et la validation refusait tout (`unknownGameOption`, 06/11). `Project.game_options` ignore désormais les clés inconnues.
