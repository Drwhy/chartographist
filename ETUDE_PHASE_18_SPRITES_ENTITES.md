# Phase 18 — Tuiles de terrain et sprites d'entités transparents

## Décision

Le rendu Canvas sépare désormais deux responsabilités visuelles :

- les tuiles de terrain couvrent toute la case et forment le fond continu ;
- les sprites d'entités utilisent des feuilles RGBA distinctes et une échelle
  inférieure à la case ; les personnages restent ancrés bas-centre tandis que
  les structures sont centrées dans les deux axes.

Le contrat reste piloté par les mêmes clés sémantiques que le terminal. Aucune
règle de simulation, priorité ou décision aléatoire ne dépend des pixels.

> État au 29 août 2026 : lots 18.0 à 18.4 livrés. Le thème historique
> à atlas unique reste compatible ; Interwoven utilise une feuille terrain
> 8 × 8 et une feuille d'entités transparente 6 × 4.

## Contrat de manifeste

Un manifeste historique sans `sheets` est normalisé vers une feuille
`default` de taille complète. Un manifeste multicouche peut déclarer :

- plusieurs PNG sûrs et locaux au thème ;
- pour chaque feuille : dimensions de cellule, grille, présence d'alpha,
  échelle et ancrage par défaut ;
- pour chaque clé visuelle : feuille, coordonnées et surcharges bornées.
- pour une entité mobile : miroir horizontal optionnel `auto_mirror` et
  variantes plates direction/état/frame, sans nouvelle image obligatoire.

Une entité réduite exige une feuille déclarée avec canal alpha. Les chemins,
dimensions, références, échelles et ancres sont validés avant exposition HTTP.
Le serveur ne sert que les PNG effectivement déclarés.

## Feuille Interwoven

- `atlas.png` reste la feuille de tuiles carrées 156 × 156 ;
- `entities.png` est une feuille RGBA 1536 × 1024, en 6 × 4 cellules de
  256 × 256 ;
- `ocean.png` est une tuile carrée RGB 1254 × 1254 dédiée à
  `terrain.ocean`, sans côte ni entité ;
- `beach.png` est une tuile carrée RGB 1254 × 1254 de sable côtier,
  utilisée par `terrain.shore` et l'alias `terrain.beach` ;
- humains et animaux occupent 70 % de la case et sont ancrés en bas au centre ;
- les structures génériques sont centrées et limitées à 68 % de la case ;
- `cultures.png` ajoute quatre villes et quatre villages distincts pour
  Empire, Sultanat, Dynastie et Clans, sans modifier les glyphes du terminal ;
- structures et véhicule peuvent surcharger leur échelle ;
- `entity.vehicle.boat` représente pêcheurs et colons lorsqu'ils naviguent.

La feuille d'entités a été générée avec OpenAI ImageGen le 27 août 2026. Prompt
final : grille stricte 6 × 4 de structures, métiers, bateau, animaux et entités
spéciales, pixel art cohérent, sujets isolés, aucun texte ni décor de case,
arrière-plan réellement transparent et marge autour de chaque silhouette.

## Lots

### Lot 18.0 — Caractérisation et compatibilité — socle terminé

1. Préserver le contrat de manifeste v1 et ses thèmes à atlas unique.
2. Conserver les clés sémantiques et l'ordre terrain → eau → route → site →
   entité.
3. Tester le contrat JavaScript sans navigateur complet.

### Lot 18.1 — Feuilles séparées — terminé

1. Valider plusieurs PNG par thème, dont les feuilles océan et plage, et leurs grilles.
2. Charger les feuilles en parallèle côté navigateur.
3. Filtrer strictement leurs routes HTTP.

### Lot 18.2 — Sprites transparents et ancrage — terminé

1. Dessiner le terrain à 100 % de la case.
2. Borner l'échelle des entités entre 10 et 100 %.
3. Ancrer les entités sans masquer le fond.
4. Refuser une entité réduite sur une feuille sans alpha.

### Lot 18.3 — Variantes sémantiques — socle terminé

1. Distinguer la navigation en bateau de la profession terrestre.
2. Couvrir villes et villages par culture, ruines, métiers, animaux et entités
   spéciales.
3. Étendre ensuite les variantes transport, chargement, blessure et activité
   sans déduire l'état depuis un glyphe.

### Lot 18.4 — Orientations et animations — terminé

1. `Entity.pos` mémorise une des huit directions lors d'un déplacement, sans
   PRNG ; le snapshot la publie à côté de la clé de base.
2. Le client détecte les changements de position entre snapshots/deltas et
   anime pendant 375 ms au maximum, sans ajouter d'état ni de travail cyclique
   au moteur.
3. Un thème peut déclarer jusqu'à huit clés contiguës
   `<base>.<direction>.<idle|moving>.frame_N`. Le fallback essaie frame
   courante, frame 0, direction, puis clé de base.
4. Interwoven active `auto_mirror` pour ses humains, animaux et bateau :
   les directions ouest sont retournées sans dupliquer la feuille.
5. `prefers-reduced-motion` impose la frame 0, supprime le rebond et ne
   programme aucune boucle Canvas supplémentaire.

### Lot 18.5 — Modding et stabilisation — socle terminé

1. **GUIDE_TILESETS.md** documente un thème multicouche minimal et
   **tools/tileset_scaffold.py** génère un exemple partiel RGB/RGBA chargeable
   sans dépendance externe.
2. Le manifeste conserve une couverture **complete** par défaut et accepte
   explicitement **coverage: partial** avec **fallback.unknown** obligatoire.
   Les anciens thèmes complets restent inchangés.
3. Le lecteur PNG borne taille, dimensions et pixels, refuse les encodages non
   RGB/RGBA 8 bits et l'entrelacement, puis vérifie structure, CRC, IDAT, IEND,
   troncature et octets surnuméraires.
4. Le banc **tools/presentation_benchmark.py** mesure la mémoire sur un passage
   dédié, arrête **tracemalloc**, puis chronomètre sans avancer la simulation ni
   consommer le PRNG. Sur la graine 1850, sept itérations :
   - 60 × 30 : pipeline médian 16,158 ms, maximum 18,474 ms, dont projection
     12,519 ms, sérialisation 2,783 ms et delta 0,643 ms ; snapshot
     505 597 octets, pic tracé 2 081 490 octets ;
   - 120 × 60 : pipeline médian 59,785 ms, maximum 66,473 ms, dont projection
     49,077 ms, sérialisation 8,767 ms et delta 2,117 ms ; snapshot
     1 982 413 octets, pic tracé 7 303 297 octets.
5. Le client expose un diagnostic borné à 600 frames qui mesure FPS actifs,
   intervalles, coût réel de dessin et cellules visibles sans déclencher de
   frame supplémentaire. Les pauses de plus de 250 ms ne polluent pas le
   calcul. Un benchmark explicite de 500 à 10 000 ms peut provoquer une
   séquence continue et reproductible ; il ne tourne jamais automatiquement.
6. La campagne de non-régression compte 512 tests. Le pipeline respecte les
   budgets maximums de 25 ms sur 60 × 30 et 75 ms sur 120 × 60. La mesure FPS
   réelle dans un navigateur reste la dernière étape de stabilisation.
7. Les options i18n `--width` et `--height` permettent désormais de lancer les
   deux tailles sans modifier le code. Un parcours réel 120 × 60 sur la graine
   88574 confirme 7 200 cellules servies. Après 240 cycles, l'audit exhaustif
   trouve 105 cellules de route, 72 de rivière et zéro connexion cardinale
   absente de la variante projetée.

## Critères de sortie

- le terrain reste visible sous toute entité mobile ;
- une transition terre/eau change de sprite sans changer l'identité ;
- un ancien thème à atlas unique reste fonctionnel ;
- aucun PNG non déclaré n'est servi ;
- le terminal conserve ses glyphes tandis que le web utilise uniquement les thèmes de sprites ;
- animations désactivées ne consomment aucun coût par cycle de simulation.
