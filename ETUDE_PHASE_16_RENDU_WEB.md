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
doivent utiliser les deltas. Validation actuelle : 437 tests complets.

## Lot 16.3 livré — serveur et protocole local

- `requirements-web.txt` garde `aiohttp` optionnel et tous les imports serveur
  restent paresseux ;
- `--renderer web --host --port --tick-speed` sélectionne le nouvel
  adaptateur sans initialiser le terminal ;
- l'API `/api/v1` sert métadonnées, snapshot et inspection d'entité ;
- les commandes HTTP/WebSocket passent par la file bornée de `SimulationHost` ;
- le flux commence par un snapshot puis publie des deltas versionnés ou une
  resynchronisation complète ;
- écoute non locale, origines étrangères, commandes inconnues, chemins clients
  et corps supérieurs à 64 Kio sont refusés ;
- la page statique minimale prépare le lot 16.4 sans chaîne de compilation.

Validation réelle : serveur lancé sur `127.0.0.1:9016`, page HTML,
métadonnées et snapshot 60 × 30 servis avec succès. Validation automatisée :
437 tests.

## Lot 16.4 livré — navigation navigateur

- le client statique sans compilation rend les seules cellules visibles dans un
  Canvas et conserve le glyphe comme fallback ;
- zoom borné, déplacement souris/tactile/clavier et sélection de cellule
  n'accèdent qu'au snapshot public ;
- pause, reprise, pas-à-pas et vitesse utilisent les commandes filtrées du
  protocole, avec repli HTTP si le WebSocket est momentanément indisponible ;
- les journaux et panneaux structurés exposent systèmes, chroniques, diplomatie,
  explications, économie, climat, sites, artefacts, politique, territoire,
  migrations, guerre et paix ;
- la reconnexion exponentielle resynchronise les révisions divergentes sans
  perturber le propriétaire du moteur ;
- l'interface est responsive, pilotable au clavier, compatible avec la réduction
  des animations et localisée par les catalogues fr/en/es.

Validation automatisée : 440 tests. Validation HTTP réelle sur
127.0.0.1:9016 : HTML, JavaScript, métadonnées localisées et snapshot
60 × 30 servis avec succès.

## Lot 16.5 livré — spritesheets data-driven

- core/tilesets.py fige 42 clés visuelles standard et valide version, identifiant,
  chemin PNG, dimensions, grille, coordonnées, couverture, fallback et licence ;
- la découverte ignore défensivement tout thème invalide et le serveur ne sert
  que le manifeste et l'image déclarée d'un thème valide ;
- l'atlas classique 8 × 8 couvre terrains, rivière, route, sites, structures,
  professions, faune, UFO et fallbacks génériques ;
- le Canvas compose terrain, hydrologie, infrastructure, site puis entité sans
  recalculer de règle métier ;
- les clés spécialisées inconnues remontent vers leur catégorie puis vers
  fallback.unknown, de sorte qu'un mod reste visible ;
- le sélecteur conserve les glyphes par défaut et charge le PNG une seule fois
  lors du passage au thème sprites.

Validation automatisée : 443 tests. Validation HTTP réelle : capability,
catalogue, manifeste de 42 sprites et PNG de 2,7 Mio servis correctement.

## Lots 16.6–16.7 livrés — optimisation et stabilisation

- l'hôte peut avancer sans construire de snapshot lorsqu'aucun client web n'est
  connecté, tout en conservant une révision strictement monotone ;
- le premier client revenu reçoit un état cohérent puis les cycles suivants
  reprennent sous forme de deltas ;
- le client maintient un index de cellules et applique chaque delta en O(k), sans
  recopier ni réindexer les 1 800 cellules de la carte ;
- le comportement historique reste le défaut : `SimulationHost.tick()` publie
  toujours un snapshot tant que l'appelant ne demande pas explicitement de le
  différer ;
- sur 60 × 30 avec toutes les options, la médiane mesurée est de 41,06 ms pour
  une projection complète, 15,31 ms pour sa sérialisation JSON et 3,73 ms pour
  le calcul d'un delta ; les payloads médians sont de 314,8 Kio et 53,5 Kio ;
- trois campagnes de 1 200 cycles (graines 1661, 1667 et 1673) terminent sans
  extinction en 35,9 s cumulées.

Validation finale : 446 tests, syntaxe JavaScript vérifiée, contrôle Git des
espaces réussi et validation HTTP réelle de la page, des métadonnées, du
snapshot ainsi que des commandes pause, pas-à-pas et reprise sur
`127.0.0.1:9016`.

## Extension livrée — thème Interwoven et bordures harmonisées

- le nouvel atlas `interwoven` mesure 1248 × 1248, forme une grille 8 × 8 de
  sprites strictement carrés de 156 × 156 et couvre les 42 clés standard ;
- son manifeste active explicitement `edge_blending.mode = interlaced`, avec
  profondeur et opacité bornées ;
- le Canvas mélange seulement les terrains différents sur leurs bordures haute
  et gauche, selon un profil spatial déterministe sans `Math.random` ;
- les couches rivière, route, site et entité restent dessinées après la
  transition afin de conserver leur lisibilité ;
- le thème classique reçoit le mode neutre `none` par défaut et ne régresse pas ;
- le nom du nouveau thème est localisé dans les catalogues fr/en/es.

La séparation entre tuiles de fond et sprites transparents d'entités est portée
par la phase 18 et [`ETUDE_PHASE_18_SPRITES_ENTITES.md`](ETUDE_PHASE_18_SPRITES_ENTITES.md).
Elle étend les manifestes sans modifier les contrats sémantiques livrés ici.

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
