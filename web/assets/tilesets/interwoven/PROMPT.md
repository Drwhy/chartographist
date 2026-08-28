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
