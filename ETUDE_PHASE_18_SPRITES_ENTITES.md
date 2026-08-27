# Phase 18 — Tuiles de terrain et sprites d'entités transparents

## Décision

Le rendu Canvas sépare désormais deux responsabilités visuelles :

- les tuiles de terrain couvrent toute la case et forment le fond continu ;
- les sprites d'entités utilisent une feuille RGBA distincte, une échelle
  inférieure à la case et un ancrage bas-centre laissant le terrain visible.

Le contrat reste piloté par les mêmes clés sémantiques que le terminal. Aucune
règle de simulation, priorité ou décision aléatoire ne dépend des pixels.

> État au 27 août 2026 : socle des lots 18.0 à 18.3 livré. Le thème historique
> à atlas unique reste compatible ; Interwoven utilise une feuille terrain
> 8 × 8 et une feuille d'entités transparente 6 × 4.

## Contrat de manifeste

Un manifeste historique sans `sheets` est normalisé vers une feuille
`default` de taille complète. Un manifeste multicouche peut déclarer :

- plusieurs PNG sûrs et locaux au thème ;
- pour chaque feuille : dimensions de cellule, grille, présence d'alpha,
  échelle et ancrage par défaut ;
- pour chaque clé visuelle : feuille, coordonnées et surcharges bornées.

Une entité réduite exige une feuille déclarée avec canal alpha. Les chemins,
dimensions, références, échelles et ancres sont validés avant exposition HTTP.
Le serveur ne sert que les PNG effectivement déclarés.

## Feuille Interwoven

- `atlas.png` reste la feuille de tuiles carrées 156 × 156 ;
- `entities.png` est une feuille RGBA 1536 × 1024, en 6 × 4 cellules de
  256 × 256 ;
- humains et animaux occupent 70 % de la case et sont ancrés en bas au centre ;
- structures et véhicule peuvent surcharger leur échelle ;
- `entity.vehicle.boat` représente pêcheurs et colons lorsqu'ils naviguent.

La feuille d'entités a été générée avec OpenAI ImageGen le 27 août 2026. Prompt
final : grille stricte 6 × 4 de structures, métiers, bateau, animaux et entités
spéciales, pixel art cohérent, sujets isolés, aucun texte ni décor de case,
arrière-plan réellement transparent et marge autour de chaque silhouette.

## Lots

### Lot 18.0 — Caractérisation et compatibilité — socle terminé

1. Préserver le manifeste v1 historique et le thème Classic.
2. Conserver les clés sémantiques et l'ordre terrain → eau → route → site →
   entité.
3. Tester le contrat JavaScript sans navigateur complet.

### Lot 18.1 — Feuilles séparées — terminé

1. Valider plusieurs PNG par thème et leurs grilles.
2. Charger les feuilles en parallèle côté navigateur.
3. Filtrer strictement leurs routes HTTP.

### Lot 18.2 — Sprites transparents et ancrage — terminé

1. Dessiner le terrain à 100 % de la case.
2. Borner l'échelle des entités entre 10 et 100 %.
3. Ancrer les entités sans masquer le fond.
4. Refuser une entité réduite sur une feuille sans alpha.

### Lot 18.3 — Variantes sémantiques — socle terminé

1. Distinguer la navigation en bateau de la profession terrestre.
2. Couvrir villes, villages, ruines, métiers, animaux et entités spéciales.
3. Étendre ensuite les variantes transport, chargement, blessure et activité
   sans déduire l'état depuis un glyphe.

### Lot 18.4 — Orientations et animations — planifié

1. Ajouter directions et frames optionnelles sans modifier les clés de base.
2. Respecter `prefers-reduced-motion`.
3. Borner cadence, mémoire GPU et nombre d'images chargées.

### Lot 18.5 — Modding et stabilisation — planifié

1. Documenter un thème multicouche minimal.
2. Tester thèmes partiels, fallback, PNG hostiles et grandes cartes.
3. Mesurer FPS et mémoire puis exécuter la campagne de non-régression.

## Critères de sortie

- le terrain reste visible sous toute entité mobile ;
- une transition terre/eau change de sprite sans changer l'identité ;
- un ancien thème à atlas unique reste fonctionnel ;
- aucun PNG non déclaré n'est servi ;
- glyphes, thèmes Classic et Interwoven conservent les mêmes priorités ;
- animations désactivées ne consomment aucun coût par cycle de simulation.

