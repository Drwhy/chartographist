# Prompt de génération — Chartographist Interwoven

Généré avec l'outil intégré OpenAI ImageGen le 26 août 2026.

```text
Use case: stylized-concept
Asset type: final production game spritesheet / tile atlas
Primary request: generate a mathematically strict square 8x8 sprite atlas. Think of a spreadsheet with exactly 8 columns and exactly 8 rows: every cell is the same independent square size, one sprite per cell, no cell can span or merge with another.
Subject order by rows: Row 1 volcano | sharp peak | high mountain | mountain | sand | glacier | boreal forest | temperate forest. Row 2 autumn forest | tropical forest | grassland | tundra | desert | cactus land | river | stone road. Row 3 battlefield | ancient ruins | sanctuary | mine | walled city | village | ruined building | unknown marker. Row 4 farmer | fisherman | hunter | settler | soldier | trader | generic human | generic structure. Row 5 wolf | bear | deer | eagle | shark | fish | rabbit | generic animal. Row 6 UFO | mysterious special entity | moss edge texture | sand edge texture | snow edge texture | water edge texture | forest edge texture | stone edge texture. Rows 7 and 8: sixteen independent subtle fantasy terrain transition textures.
Style/medium: crisp handcrafted retro pixel art for a top-down simulation game, limited cohesive earthy fantasy palette, readable silhouettes, dense intentional pixel clusters.
Composition/framing: exact uniform square grid geometry, each terrain texture fills only its own square edge-to-edge, each entity centered only within its own square. Final image square, direct atlas view, flat front-facing image plane.
Constraints: EXACTLY 8 columns and 8 rows; EXACTLY 64 equal square cells; no merged areas; no irregular mosaic; no perspective; no mockup; no gutters; no margins; no visible separator lines; no rounded tiles; no labels; no letters; no numbers; no text; no logo; no watermark.
```

La sortie 1254 × 1254 a été recadrée symétriquement de trois pixels par bord,
sans rééchantillonnage, pour obtenir l'atlas final 1248 × 1248 et ses cellules
de 156 × 156.

## Tuile océan autonome

Générée avec l'outil intégré OpenAI ImageGen le 27 août 2026 et enregistrée
sous `ocean.png` (1254 × 1254, RGB).

```text
Use case: stylized-concept
Asset type: final production game terrain tile for Chartographist Interwoven
Primary request: create exactly one square seamless deep-ocean terrain tile that can repeat edge-to-edge as the full background of map cells.
Input image: use the displayed Interwoven atlas preview as the style reference only; match its crisp handcrafted retro pixel art, pixel density, lighting, cohesive earthy-fantasy palette, and top-down/front-facing flat game-tile treatment.
Subject: open ocean water only, rich deep blue and teal wave patterns with subtle foam highlights and natural pixel-cluster variation.
Composition/framing: one single square tile filling the entire canvas edge-to-edge; visually seamless on all four edges; no grid and no margins.
Constraints: terrain background only; no coast, no beach, no land, no islands, no riverbanks, no boats, no fish, no animals, no people, no structures, no border, no rounded corners, no transparency, no text, no logo, no watermark.
```

## Tuile de plage autonome

Générée avec l'outil intégré OpenAI ImageGen le 28 août 2026 et enregistrée
sous `beach.png` (1254 × 1254, RGB).

```text
Use case: stylized-concept
Asset type: final production game terrain tile for Chartographist Interwoven
Primary request: create exactly one square seamless beach-sand terrain tile that can repeat edge-to-edge as the full background of coastal map cells.
Input images: use the displayed Interwoven atlas and deep-ocean tile only as style and palette references; match their crisp handcrafted retro pixel art, pixel density, lighting, cohesive earthy-fantasy palette, and top-down/front-facing flat game-tile treatment.
Subject: warm golden coastal sand with subtle wet-sand tonal variation, sparse tiny shells and smooth pebbles rendered as restrained pixel clusters.
Composition/framing: one single square tile filling the entire canvas edge-to-edge; visually seamless on all four edges; evenly distributed detail without a focal object, grid, margin, or directional shoreline.
Constraints: beach terrain background only; no ocean water, no waves, no coast line, no dunes, no vegetation, no palm trees, no driftwood, no animals, no people, no structures, no border, no rounded corners, no transparency, no text, no logo, no watermark.
```

## Refonte des terrains et variantes climatiques

Les sources ont été générées avec l'outil intégré OpenAI ImageGen le
28 août 2026, puis assemblées par `tools/build_interwoven_tiles.py` dans
`climate.png`. Le découpage mécanique recentre chacune des 14 cellules et la
ramène exactement à 156 × 156. La feuille finale mesure 1092 × 2496, soit
7 colonnes et 16 lignes : deux lignes pour chacune des variantes hiver,
printemps, été, automne, sécheresse, crue, vague de chaleur et vague de froid.

Prompt de base :

```text
Use case: stylized-concept
Asset type: final production game terrain source atlas for Chartographist Interwoven
Primary request: remake the complete terrain tileset as a mathematically strict 7 columns by 2 rows atlas, exactly fourteen equal cells.
Subject order: volcano | peak | high mountain | mountain | sand | glacier | boreal forest; temperate forest | autumn forest | tropical forest | grassland | tundra | desert | cactus land.
Style/medium: crisp handcrafted top-down retro pixel art, cohesive earthy fantasy palette and consistent texture scale.
Constraints: preserve clean cell boundaries; no text, entity, river, road, ocean, logo or watermark.
```

Chaque passe saisonnière utilise le mode `lighting-weather` avec la contrainte
suivante répétée :

```text
Change only seasonal appearance; preserve the same 7x2 geometry, terrain
structures, camera, framing, object placement and texture scale. Each tile must
remain visibly the same place in the requested season.
```

Les anomalies sont des transformations colorimétriques bornées des mêmes
cellules ; elles ne déplacent aucun détail et évitent donc toute rupture
d'identité lors d'un changement de climat.

## Rivières connectées

`rivers.png` est une feuille RGBA 4 × 3 de cases 156 × 156. Elle contient les
formes verticale, horizontale, quatre coudes, quatre fourches et la croix. Tous
les bras rejoignent exactement le centre du bord concerné ; la transparence
laisse le terrain et sa variante climatique visibles sous la rivière.

La source `sources/rivers-source.png` a été générée avec ImageGen intégré le
28 août 2026, puis normalisée sans retouche sémantique par
`tools/build_interwoven_tiles.py`. Prompt final :

```text
Create a production-ready transparent PNG sprite atlas for a top-down 2D
world-map simulation, matching a handcrafted high-detail pixel-art fantasy
cartography style. Exact layout: 4 columns by 3 rows, 12 equal square cells,
no gutters, no border, no labels, transparent background in every cell.
Draw the same narrow natural river in all cells: deep teal-blue water, pale
cyan highlights and subtle dark earthy/rocky banks. Every arm must meet the
exact midpoint of the relevant cell edge with identical width. Order:
vertical, horizontal, NE, NW / SE, SW, N-E-W, N-E-S /
E-S-W, N-S-W, cross, empty. Orthographic top-down, crisp pixel edges,
coherent scale, no text and true alpha transparency.
```

## Routes connectées

`roads.png` suit exactement le même contrat 4 × 3 et le même ordre de
topologies. Sa source reproductible est `sources/roads-source.png`.
La source générée ne respecte toutefois pas les quatre orientations de coude :
le manifeste utilise donc le coude NE vérifié en (2, 0) comme source canonique
et applique des rotations déclaratives de 0°, 90°, 180° et 270° pour garantir
respectivement les raccords NE, SE, SW et NW. Les lignes, fourches et la croix
conservent leurs cellules, contrôlées sur les quatre bords.

```text
Create a production-ready transparent 4x3 PNG sprite atlas for a top-down 2D
world-map simulation in the same handcrafted detailed pixel-art fantasy
cartography style. Draw a modest-width old earthen road with warm ochre
compacted dirt, irregular small tan stones and restrained wheel ruts, without
terrain background. Every arm meets the exact midpoint of its edge at
identical width. Order: vertical, horizontal, NE, NW / SE, SW, N-E-W,
N-E-S / E-S-W, N-S-W, cross, empty. No labels, shadows or text; true alpha.
```

## Établissements culturels

`cultures.png` est une feuille RGBA 4 × 2 de cellules 256 × 256. Les colonnes
représentent Empire, Sultanat, Dynastie et Clans ; les lignes représentent
villes puis villages. Les silhouettes sont centrées et le manifeste limite
leur taille affichée à 68 % ou moins.

```text
Create a polished transparent 4x2 PNG sprite atlas for a top-down fantasy
world-map simulation, coherent with handcrafted detailed pixel-art terrain,
rivers and roads. Each building is centered in its cell with one consistent
orthographic three-quarter camera. Columns: fortified stone Empire,
sandstone-and-turquoise Sultanat, red-roof timber Dynastie, Nordic Clans
palisade and turf roofs. Rows: compact city, then small village. No people,
text, terrain patches, snow or water; true alpha transparency.
```

`water-climate.png` applique les huit mêmes variantes à l'océan et au rivage
issus de la section `water`. Cette feuille RGBA mesure 312 × 1248 et conserve
elle aussi des cases strictes de 156 × 156.
