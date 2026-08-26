# Phase 16 — Étude de faisabilité du rendu web et par sprites

## Décision proposée

La phase est **faisable sans modifier les règles de simulation**. Le moteur
`SimulationEngine` est déjà indépendant du terminal, déterministe et pilotable
cycle par cycle. Le navigateur sera un nouvel adaptateur sélectionné par
`--renderer web`, tandis que le terminal restera le mode par défaut.

Le point d'architecture central sera une projection de présentation versionnée,
immuable et sérialisable. Elle traduira `world` et `stats` en cellules
sémantiques, panneaux et événements. Le terminal et le navigateur consommeront
ce contrat ; la spritesheet ne contiendra donc aucune règle métier.

Architecture cible :

`CLI → SimulationHost → SimulationEngine → PresentationProjector → Snapshot v1`

Le snapshot alimente soit l'adaptateur terminal, soit un serveur local HTTP et
WebSocket. Dans le navigateur, un même client choisit le thème glyphes ou le
thème spritesheet/Canvas. Les commandes validées reviennent au
`SimulationHost`, jamais directement au moteur.

## État actuel favorable

- `SimulationEngine.create()`, `step()` et `run()` ne dépendent ni du rendu
  ni de la temporisation.
- Les identifiants d'entités, chroniques, sites, artefacts et légendes sont
  stables ; ils peuvent devenir les clés publiques de l'interface.
- Inspection, systèmes, diplomatie, histoire causale et interface « Pourquoi ? »
  ont déjà des lectures headless défensives.
- La carte est petite par défaut (60 × 30) et un index des entités par position
  existe déjà dans le rendu terminal.
- Le terminal peut rester disponible pendant toute l'implémentation.

## Points bloquants ou risqués

| Point | Impact | Réponse technique |
|---|---|---|
| `main.py` mélange boucle, cadence, clavier, ANSI et sauvegarde | cycle de vie non réutilisable | extraire un `SimulationHost` indépendant |
| Les fonctions `render/ui_*.py` impriment directement | données inutilisables par le web | projeter des DTO JSON avant de rendre |
| `biome_at()`, `Entity.char` et les sites renvoient des glyphes | un emoji n'est pas une identité de sprite | ajouter des clés sémantiques sans retirer `char` |
| `world` contient NumPy, objets Python, graphes cycliques et services | sérialisation JSON directe impossible | liste blanche stricte dans le projecteur |
| Le moteur et les registres globaux ne sont pas thread-safe | snapshot incohérent ou PRNG perturbé | un seul thread possède et avance le moteur |
| `Translator` et plusieurs catalogues sont globaux | plusieurs langues/mondes se contamineraient | un monde et une langue par processus en phase 16 |
| Les glyphes ont des largeurs Unicode variables | grille sprite impossible depuis le texte | cellules indexées par coordonnées |
| Le checkpoint est un pickle de confiance | exposition web dangereuse | aucune route d'upload ou de lecture pickle |
| Aucune pile HTTP n'est installée | dépendance supplémentaire | dépendance web optionnelle et import paresseux |
| Les panneaux du bestiaire sont orientés texte | duplication probable | API de panneaux structurés sur les services existants |
| Un snapshot complet à chaque frame serait coûteux | gêne sur matériel modeste | état initial puis deltas, fréquence plafonnée |

Le risque principal est la divergence entre deux logiques visuelles si la
priorité entité → site → route → rivière → terrain est recodée en JavaScript.

## Architecture technique

### Hôte de simulation

`SimulationHost` possède l'unique moteur ainsi que `running`, `paused`,
`tick_interval` et `revision`. Il vide une file de commandes bornée, appelle
`step()`, puis publie un snapshot à la frontière du cycle. Les commandes
initiales sont pause, reprise, pas-à-pas, vitesse bornée et sélection. Une
sauvegarde n'utilise que le chemin fourni au lancement.

### Contrat de présentation

`presentation.schema_version = 1` exposera révision, cycle, horloge,
dimensions, cellules, logs, systèmes et sélection. Une cellule contient
`x`, `y`, `terrain_key`, `infrastructure_key`, `site_key`, une entité
publique optionnelle et `visible_key`.

Chaque entité projetée expose seulement `entity_id`, `render_key`,
`z_index`, position, catégorie et indicateurs publics. Les détails passent par
`inspect_entity()`. Les valeurs NumPy deviennent des nombres Python.

`VisualCellResolver` sera l'unique propriétaire de la priorité des couches.
Le terminal traduira `visible_key` en glyphe historique ; le navigateur le
traduira en sprite. Un test de compatibilité comparera chaque cellule à
`get_char_at()` avant de basculer le terminal.

### Serveur local et protocole

Choix recommandé : `aiohttp`, importé uniquement avec `--renderer web`. Il
sert les fichiers statiques, les routes REST de lecture et un WebSocket. Cette
option est plus légère que FastAPI, gère arrêt et déconnexion et permet les
deltas sans polling.

API proposée :

- `GET /api/v1/meta` : version, capacités et informations du monde ;
- `GET /api/v1/snapshot` : état initial ou resynchronisation ;
- `GET /api/v1/entities/{id}` : inspection défensive ;
- `GET /api/v1/history`, `/systems`, `/why` : façades existantes ;
- `GET /api/v1/stream` en WebSocket : snapshots, deltas et commandes ;
- `GET /` : application statique locale.

Le serveur écoute `127.0.0.1` par défaut. Une écoute externe demande une
option explicite et un avertissement. Les messages ont un schéma, une taille
maximale et une liste blanche. Aucun objet Python, chemin libre ou pickle n'est
exposé.

Options prévues : `--renderer terminal|web`, `--host 127.0.0.1`,
`--port 8765`, `--tick-speed 0.15`, `--open-browser` et
`--tileset default`.

### Client navigateur

Le premier client utilisera HTML, CSS et modules JavaScript statiques pour
éviter une chaîne de build. Le DOM portera les panneaux accessibles et un Canvas
la carte. Il offrira zoom, déplacement, centrage, sélection par tuile/entité,
en-tête, logs, chroniques, diplomatie, systèmes, « Pourquoi ? », pause,
pas-à-pas, vitesse et reconnexion par révision.

Le navigateur ne décide jamais d'un biome, d'un z-index ou d'un état métier.

### Spritesheet à la Dwarf Fortress

Le rendu sprite sera un thème, pas un second moteur. Un manifeste
`assets/tilesets/<id>/tileset.json` associera les clés sémantiques à un atlas
PNG, avec version, image, dimensions de tuile, coordonnées et fallback.

Le Canvas dessine terrain, infrastructure, site puis entité. Les variantes
culturelles utilisent une teinte ou une clé spécialisée ; les états bateau,
transport, ruine envahie ou ville fortifiée ont des clés explicites. Un fallback
garantit qu'un mod inconnu reste visible. Chaque tileset porte sa licence et un
test automatisé de couverture des clés standard.

## Socle de vigilance réalisé — 26 août 2026

Les risques préalables aux travaux web sont désormais traités dans le noyau :

- `VisualCellResolver` possède l'unique priorité terrain → rivière → route →
  site → entité et conserve les glyphes terminaux historiques ;
- `PresentationProjector` produit un contrat JSON v1 en liste blanche, refuse
  les objets Python inconnus, borne journaux/chroniques et ne tire pas le PRNG ;
- les dix-huit panneaux structurés rendent observables les systèmes influents ;
- `snapshot_delta()` borne les changements et impose une resynchronisation si
  le budget est dépassé ;
- `SimulationHost` réserve les mutations au thread propriétaire, sérialise une
  file bornée et limite la sauvegarde au chemin fourni au lancement ;
- le terminal passe par le même résolveur et reste le mode sans dépendance web.

Budget mesuré avec `template-all.json` et `tracemalloc` : 30 × 15 en 11,47 ms
de projection, 3,50 ms de JSON et 0,71 Mio de pic ; 60 × 30 en 32,14 ms,
13,14 ms et 1,94 Mio ; 120 × 60 en 124,55 ms, 51,85 ms et 7,45 Mio. La cible
60 × 30 est compatible avec une publication plafonnée ; les grandes cartes
doivent utiliser les deltas. Validation : 425 tests complets.

## Plan d'implémentation TDD

### Lot 16.0 — Caractérisation et budgets

1. Figer par tests les priorités et états visuels actuels.
2. Mesurer projection, JSON, FPS et mémoire sur plusieurs tailles.
3. Écrire l'ADR du protocole, de la dépendance et du modèle mono-monde.

### Lot 16.1 — Projection sémantique

1. Introduire DTO, `render_key` rétrocompatible et `VisualCellResolver`.
2. Construire snapshot, index et copies défensives.
3. Vérifier zéro tirage PRNG et égalité avec le terminal.
4. Ajouter version de schéma, limites et validation.

### Lot 16.2 — Hôte et cycle de vie

1. Extraire de `main.py` cadence, pause, pas-à-pas et arrêt.
2. Conserver le chemin terminal par défaut à l'identique.
3. Ajouter file de commandes bornée et publication après cycle.
4. Couvrir arrêt, sauvegarde, exception, reprise et déterminisme.

### Lot 16.3 — Serveur web local

1. Servir client, métadonnées, snapshot et inspections.
2. Ajouter WebSocket, séquences, reconnexion et deltas.
3. Valider commandes, origine, tailles, bind et fermeture.
4. Tester l'absence de dépendance web en mode terminal.

### Lot 16.4 — Navigation navigateur

1. Carte Canvas glyphes, zoom, déplacement et sélection.
2. En-tête, logs et panneaux structurés.
3. Chroniques, diplomatie, systèmes et « Pourquoi ? ».
4. Accessibilité clavier, responsive et langues fr/en/es.

### Lot 16.5 — Pipeline spritesheet

1. Geler le catalogue des clés visuelles.
2. Valider manifeste, dimensions, coordonnées, fallback et licence.
3. Ajouter un atlas minimal couvrant toutes les clés standard.
