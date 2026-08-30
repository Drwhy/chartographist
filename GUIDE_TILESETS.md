# Créer un tileset pour Chartographist

Le navigateur découvre au démarrage les dossiers placés dans
**web/assets/tilesets/**. Chaque dossier contient un **tileset.json** et
uniquement les PNG locaux déclarés par ce manifeste. Le validateur de référence
est **core/tilesets.py**.

## Démarrer avec un exemple fonctionnel

Le générateur **tools/tileset_scaffold.py** crée un thème multicouche sans
dépendance externe :

~~~python
from tools.tileset_scaffold import create_minimal_tileset

create_minimal_tileset("web/assets/tilesets/mon-theme")
~~~

Il produit :

- **terrain.png**, feuille RGB de deux cellules 16 × 16 ;
- **entities.png**, feuille RGBA transparente d’une cellule 16 × 16 ;
- **tileset.json**, manifeste partiel avec fallback, licence, échelle, ancrage
  et miroir directionnel.

Le dossier doit être nouveau et son nom doit respecter
**[a-z0-9][a-z0-9_-]{0,31}**. Redémarrer ensuite le serveur web pour que la
découverte prenne en compte le thème.

## Couverture complète ou partielle

Sans option, la couverture est **complete** et les 42 clés visuelles standard
sont obligatoires. Un mod volontairement incomplet déclare
**coverage: "partial"**. Il doit toujours fournir **fallback.unknown**.

Le résolveur cherche la clé la plus précise, retire progressivement ses suffixes,
puis utilise le fallback. Un thème partiel peut donc commencer avec seulement :

- **terrain.grassland** ;
- **entity.human** ;
- **fallback.unknown**.

Les clés standard et les règles de validation sont définies dans
**core/tilesets.py**.

## Feuilles et sprites

Chaque feuille déclare son PNG, la taille d’une cellule, le nombre de colonnes
et lignes, la présence d’alpha, puis éventuellement **scale**, **anchor_x** et
**anchor_y**. Un sprite référence une cellule avec **x**, **y** et **sheet**.

Les entités réduites exigent une feuille RGBA. **auto_mirror: true** permet de
retourner automatiquement le sprite vers l’ouest sans dupliquer la cellule.
Les rotations sont limitées aux quarts de tour.

Pour fournir de vraies animations, utiliser des clés plates contiguës :

**<base>.<direction>.<state>.frame_N**

Exemple :

~~~text
entity.human.trader.east.moving.frame_0
entity.human.trader.east.moving.frame_1
~~~

Les directions reconnues sont **north**, **northeast**, **east**, **southeast**,
**south**, **southwest**, **west** et **northwest**. Les états sont **idle** et
**moving**, avec huit frames consécutives au maximum. En l’absence d’une
variante, le client revient à la direction puis à la clé de base.

## Budgets de sécurité

Un PNG est refusé s’il dépasse 8192 px sur un axe, 64 Mpx, 64 Mio, s’il est
entrelacé ou s’il n’est pas RGB/RGBA 8 bits. Les chemins traversants (deux
points ou séparateurs de répertoires), références hors grille, doublons JSON,
propriétés inconnues et fichiers non déclarés sont également refusés.

## Mesurer un thème sur une grande carte

**tools/presentation_benchmark.py** mesure projection, sérialisation, delta,
pipeline total, taille du snapshot et pic mémoire sans avancer la simulation.
Le passage mémoire est séparé des chronométrages afin que **tracemalloc** ne
gonfle pas les latences :

~~~python
from tools.presentation_benchmark import benchmark_presentation

report = benchmark_presentation(engine, iterations=5)
~~~

Le rapport est composé uniquement de valeurs sérialisables. Il peut être
comparé aux mesures 60 × 30 et 120 × 60 consignées dans
**ETUDE_PHASE_18_SPRITES_ENTITES.md**.

## Mesurer les FPS Canvas réels

Lancer une nouvelle carte 120 × 60 avec les dimensions CLI bornées :

~~~bash
python main.py --renderer web --seed 88574 --width 120 --height 60 --host 127.0.0.1 --port 8765 --tick-speed 0.15
~~~

Le client conserve au plus 600 mesures en mémoire, sans créer de boucle de
rendu supplémentaire. Dans les outils de développement du navigateur,
réinitialiser le relevé, déplacer ou zoomer la carte pendant la séquence à
mesurer, puis lire le rapport :

~~~javascript
__chartographistPerformance.reset()
// déplacer ou zoomer la carte pendant la campagne
__chartographistPerformance.report()
~~~

Le rapport fournit les FPS actifs, les médiane, 95e percentile et maximum des
intervalles et du coût de dessin, ainsi que le maximum de cellules visibles.
Les pauses supérieures à 250 ms sont exclues du calcul des FPS afin que le temps
où le Canvas est volontairement au repos ne dégrade pas la mesure.

Pour une campagne reproductible, le client peut également provoquer à la
demande trois secondes de rafraîchissements continus puis retourner directement
le rapport :

~~~javascript
await __chartographistPerformance.benchmark(3000)
~~~

La durée demandée est bornée entre 500 et 10 000 ms. Cette boucle n’existe que
pendant l’appel explicite au benchmark et reste inactive en utilisation normale.

## Budgets de sortie de la phase 18

Sur une cadence de référence de 150 ms, les budgets retenus sont :

- pipeline **≤ 25 ms** au maximum sur 60 × 30 ;
- pipeline **≤ 75 ms** au maximum sur 120 × 60 ;
- FPS actifs **≥ 50** pendant le benchmark Canvas ;
- intervalle de frame au 95e percentile **≤ 25 ms** ;
- coût de dessin au 95e percentile **≤ 16,7 ms**.

Les deux campagnes doivent utiliser le même navigateur, le même viewport et le
thème Interwoven. Un échec Canvas doit être confirmé sur deux passages avant
toute optimisation.
