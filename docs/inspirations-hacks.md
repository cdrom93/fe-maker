# Mécaniques à reprendre des hacks cités (ticket 43, 29/10/2026)

L'utilisateur a cité les hacks FE8 qui lui ont plu : *Vision Quest*, *Code of the Burger King*, *The Morrow's Golden Country*,
*Andaron Saga* et *Rebellion Saga*. Ci-dessous, leurs mécaniques (d'après leurs pages FEU), et ce qu'il faudrait à FE Maker
pour les proposer. Rien n'est lancé : à choisir avec l'utilisateur.

Sources : [Vision Quest](https://feuniverse.us/t/fe8-complete-fire-emblem-vision-quest-v3-by-pushwall-1-oct-22/3815),
[Code of the Burger King](https://feuniverse.us/t/fe8-fire-emblem-code-of-the-burger-king-main-campaign-complete/13690),
[The Morrow's Golden Country](https://feuniverse.us/t/fe8-fire-emblem-the-morrows-golden-country-complete/16284).
Andaron Saga et Rebellion Saga n'ont pas de page FEU (hacks retirés) : seulement des avis de joueurs (beaucoup de contenu,
succès RetroAchievements, musique soignée) ; rien de précis à reprendre.

## Ce qui revient dans ces hacks

| Mécanique | Vu dans | Ce qu'il faudrait | Difficulté |
| --- | --- | --- | --- |
| Brouillard de guerre par chapitre (et torches qui éclairent) | Vision Quest, Morrow | Le jeu l'a déjà (réglage de vision du chapitre) : l'exposer dans l'onglet Chapitres ; torches = objets de carte | Facile |
| Promotion par objet universel | Vision Quest | Données d'objets (déjà éditables) : vérifier la liste des classes promouvables | Facile |
| Voleurs qui ouvrent sans clé (Locktouch), Vol | Vision Quest, Morrow | Capacités de classe existantes ; Locktouch = patch FEBuilder | Facile à moyen |
| Échanges à la FE5, Pousser (Shove) pour tous | Vision Quest | Patchs FEBuilder (`config/patch2/FE8U`) | Moyen |
| Talents (skills) appris par niveau, affichés sur la fiche | Vision Quest, Morrow, CotBK | Système de talents (C-SkillSys), même chantier que force/magie (#27) | Gros |
| Arts de combat à la Three Houses | Morrow | Au-dessus du système de talents | Gros |
| Soutiens à la Tellius, conversations de base, relecture des conversations | Vision Quest, Morrow | Nouvelle « base » entre chapitres (menu de préparation) ; soutiens déjà éditables | Gros |
| Reclassement (changer de classe) | CotBK | Écran de reclassement (patch existant à chercher) | Moyen à gros |
| Chapitres annexes (gaiden) débloqués par condition | Vision Quest | Page Campagne : embranchements avec condition (« si X est vivant ») | Moyen, déjà prévu (routes) |
| Cartes « survivre », « s'échapper » | Vision Quest, Morrow | Survivre existe ; « s'échapper » = objectif zone + sortie des unités | Moyen |
| Déplacement libre entre chapitres (FreeMovement) | Morrow | Patch de Mokha (moteur) | Gros |
| Difficultés et options choisies au démarrage | Morrow | Le jeu a Facile/Normal/Difficile : réglages par difficulté dans les groupes d'unités | Moyen |
| Plafonds de stats, armes et bâtons rééquilibrés | CotBK, Morrow | Déjà faisable dans FE Maker (classes, objets) | Fait |
| Écran de combat, cadres de menus, cartes de classe, icônes personnalisés | CotBK | Import d'images (phase 5) ; cartes de classe et icônes sont dans FE-Repo | Moyen |
| Salle des sons, guide en jeu | CotBK, Vision Quest | Le jeu a déjà le guide et la salle des sons : éditer leurs textes | Moyen |

## Proposition d'ordre

1. Brouillard de guerre par chapitre (déjà dans le jeu, à exposer), objectif « s'échapper ».
2. Chapitres annexes à condition, avec les routes de la page Campagne.
3. Patchs FEBuilder simples à cocher (Locktouch, Pousser, échanges FE5), dans la liste des patchs QoL (`docs/patchs-qol.md`).
4. Plus tard, avec #27 : talents, arts de combat, reclassement.
