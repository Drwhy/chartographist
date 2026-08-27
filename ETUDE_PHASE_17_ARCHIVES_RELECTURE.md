# Phase 17 — Archives portables, chronologie et relecture

## Décision proposée

La phase 17 doit rendre l'histoire déjà produite par la simulation consultable
dans le temps, sans transformer le navigateur en second moteur et sans exposer
les sauvegardes Python de confiance.

Le format recommandé est une archive de consultation `.chartarchive` fondée
uniquement sur le contrat public de présentation JSON. Elle contient des images
clés espacées et les deltas intermédiaires. Sa lecture reconstruit un état passé
sans muter `world`, sans charger de `pickle` et sans consommer le PRNG.

Cette proposition prolonge directement les phases 15 et 16 : les faits causaux
deviennent une chronologie navigable et la carte web peut montrer ce qui a
changé entre deux périodes.

## État actuel et manque utilisateur

Le projet possède déjà :

- une simulation headless déterministe et des checkpoints de reprise ;
- un snapshot JSON en liste blanche et des deltas versionnés ;
- des chroniques, causes, artefacts, sites et résumés de systèmes ;
- un client Canvas capable de reconstruire l'état courant ;
- un serveur limité à la boucle locale.

En revanche, une fois un cycle passé, l'utilisateur ne peut plus revoir la
carte correspondante. Partager un monde exige actuellement de partager un
checkpoint `pickle`, format volontairement réservé à des fichiers locaux de
confiance et fragile face aux renommages de classes.

## Périmètre

La phase couvre :

1. l'enregistrement opt-in d'états publics et de deltas ;
2. un format portable, versionné, validé et borné ;
3. la lecture headless d'une révision ou d'un cycle ;
4. une frise chronologique dans le navigateur ;
5. la comparaison visuelle de deux dates et l'accès aux faits marquants ;
6. l'export d'un récit consultable sans code exécutable.

Elle ne couvre pas :

- le retour en arrière du moteur vivant ;
- la création de branches alternatives ;
- une garantie de resimulation exacte entre versions différentes du code ;
- l'exposition réseau, le multi-utilisateur ou un service hébergé ;
- le remplacement du checkpoint `.chart` utilisé pour reprendre une partie.

## Séparation des formats

| Besoin | Format | Niveau de confiance | Effet |
|---|---|---|---|
| Reprendre la simulation | checkpoint `.chart` existant | fichier local de confiance | recharge le graphe Python et le PRNG |
| Consulter et partager l'histoire | archive `.chartarchive` | données non fiables validées | reconstruit seulement des DTO JSON |

Un bouton ou une route d'archive ne doit jamais appeler `pickle.loads`. Le
lecteur d'archive ne reçoit pas de référence vers `SimulationEngine`.

## Architecture recommandée

### Producteur

Un `ArchiveRecorder` reçoit les snapshots et deltas déjà construits par la
couche de présentation. Il reste optionnel : sans option d'enregistrement,
aucun coût d'I/O ni projection supplémentaire n'est ajouté au terminal ou au
serveur sans client.

L'enregistrement actif constitue explicitement un consommateur de présentation.
Il justifie alors la projection même en l'absence de navigateur.

### Format v1

L'archive est un ZIP sans entrée exécutable, avec chemins et tailles validés :

```text
manifest.json
keyframes/000000000001.json
segments/000000000001-000000000060.ndjson
...
```

Le manifeste contient au minimum :

- version du format d'archive et version du schéma de présentation ;
- identité publique du monde, graine et dimensions ;
- première et dernière révision, cycles couverts et intervalle des images clés ;
- liste ordonnée des membres, tailles décompressées et empreintes SHA-256 ;
- capacités enregistrées, sans chemin local ni objet Python sérialisé.

Les membres sont écrits dans un ordre canonique. Les métadonnées non
déterministes, comme la date de création, ne participent pas à l'identité
reproductible du contenu.

### Lecteur

`ArchiveReader` valide le manifeste avant toute reconstruction. Pour atteindre
une révision, il charge l'image clé précédente puis applique au plus un segment
borné de deltas. Il retourne une copie défensive conforme au snapshot public.

Les limites configurables portent sur :

- taille du fichier et taille totale décompressée ;
- nombre de membres, images clés, segments et révisions ;
- longueur d'une ligne NDJSON et nombre de cellules par delta ;
- taux de compression maximal pour éviter une bombe ZIP ;
- noms de membres normalisés, sans chemin absolu ni `..`.

### Serveur et navigateur

Le serveur ouvre une archive choisie au lancement, jamais un chemin fourni par
une requête HTTP. Le mode archive expose uniquement métadonnées et états de
lecture. Les commandes de mutation sont absentes ou refusées.

Le client réutilise le Canvas, l'index de cellules et les panneaux existants. Il
ajoute :

- un état explicite « archive » distinct du direct ;
- une frise cycle/année avec lecture, pause et vitesse locales ;
- précédent/suivant sur les chroniques importantes ;
- un mode comparaison qui surligne les cellules ajoutées, modifiées ou retirées ;
- une URL locale pouvant restaurer la révision affichée sans contenir de chemin.

Tous les nouveaux libellés passent par les catalogues fr/en/es.

## Lot 17.0 livré — caractérisation et ADR

Les mesures de phase 16 donnaient, sur 60 × 30, environ 314,8 Kio par snapshot
et 53,5 Kio par delta médian avant compression. Le benchmark dédié, graine 1700
et toutes les options actives, confirme qu'un snapshot complet à chaque cycle
doit être exclu.

Sur 1 200 cycles, les stratégies ZIP DEFLATE niveau 6 donnent :

| Intervalle | Images clés | Données JSON | Archive estimée |
|---:|---:|---:|---:|
| 30 cycles | 40 | 109,724 Mio | 7,228 Mio |
| 60 cycles | 20 | 104,288 Mio | 7,069 Mio |
| 120 cycles | 10 | 101,565 Mio | 6,988 Mio |

La projection médiane coûte 27,01 ms, le calcul du delta 2,224 ms et 155
cellules changent par cycle médian. Reconstruire exactement la révision 120
depuis l'image clé 61 et 59 deltas prend 42,935 ms en médiane et 50,123 ms au
95e percentile sur la machine de mesure.

Décision v1 : une image clé tous les 60 cycles. Passer à 120 n'économise que
0,081 Mio sur 1 200 cycles mais double le travail maximal de relecture. Les
budgets retenus restent une archive inférieure à 40 Mio, une reconstruction
inférieure à 250 ms et un surcoût médian inférieur à 10 % lorsque
l'enregistrement est actif. Le coût désactivé doit rester limité à un test de
branche sans projection ni I/O supplémentaire.

Bornes de sécurité initiales à figer par les tests du lot 17.1 : fichier de
256 Mio, contenu décompressé cumulé de 1 Gio, 10 000 membres, 100 000 révisions,
8 Mio par ligne NDJSON, 64 Mio par membre et ratio de compression maximal de
100. Les dimensions doivent être positives et leur produit ne peut dépasser
262 144 cellules. Chaque membre référencé par le manifeste porte un SHA-256.

## Plan TDD

### Lot 17.0 — Caractérisation et ADR — terminé

1. Taille, taux de changement, compression et reconstruction mesurés.
2. Snapshot public plus chaîne continue de deltas retenus comme invariant.
3. Intervalle de 60 cycles et premières limites de sécurité décidés.
4. Arbitrages de format, confiance et reproductibilité documentés ici.

### Lot 17.1 — Format et validation — terminé

1. Douze contrats TDD couvrent manifeste, membres, limites, reproductibilité et écriture atomique.
2. L'ordre des membres et leur JSON sont canoniques ; chaque contenu porte un SHA-256.
3. ZIP slip, doublons, limites, ratio de compression et JSON invalide sont rejetés.
4. Le module repose uniquement sur ZIP et JSON et ne charge aucun objet Python.

### Lot 17.2 — Enregistreur borné — terminé

1. L'hôte accepte des consommateurs optionnels sans coût de projection lorsqu'ils sont absents.
2. L'enregistreur stage les membres sur disque et ne garde qu'un segment en mémoire.
3. Images clés, rotation à 60 cycles, finalisation atomique, `Ctrl+C` et abandon sont couverts.
4. Sur 60 × 30 × 120, l'état final reste strictement identique et l'archive mesure 0,745 Mio.

### Lot 17.3 — Lecture headless — terminé

1. Révisions, cycles et bornes temporelles sont reconstruits depuis l'image clé précédente.
2. Les résultats sont défensifs et n'accèdent ni au moteur, ni au PRNG.
3. Images clés, segments, cycles et chroniques sont indexés avec continuité et limites spatiales validées.
4. La comparaison expose cellules, horloges et panneaux modifiés entre deux révisions.

### Lot 17.4 — API locale de consultation — terminé

1. `/api/v1/meta` distingue le mode archive et publie ses bornes read-only.
2. Snapshot par révision, chronologie filtrée et comparaison sont disponibles sans moteur.
3. Les contrôles d'origine, de taille et de boucle locale sont identiques au direct.
4. Les commandes sont refusées et le serveur d'archive ne crée ni ticker ni WebSocket.

### Lot 17.5 — Frise navigateur

1. Ajouter navigation temporelle accessible au clavier.
2. Réutiliser glyphes et sprites sans divergence de résolution visuelle.
3. Montrer clairement direct, archive, chargement et erreur.
4. Ajouter comparaison cartographique et raccourcis vers les faits marquants.

### Lot 17.6 — CLI, i18n et documentation

1. Ajouter des options opt-in rétrocompatibles et mutuellement cohérentes.
2. Traduire aide, erreurs, états et contrôles dans les trois catalogues.
3. Documenter création, ouverture, partage et limites de confiance.
4. Fournir un exemple minimal reproductible.

### Lot 17.7 — Performance et stabilisation

1. Tester 20 graines courtes et 3 campagnes de 1 200 cycles.
2. Mesurer espace, latence de recherche, mémoire et coût d'enregistrement.
3. Valider archives tronquées, versions inconnues et migrations autorisées.
4. Vérifier terminal, web direct, sprites, checkpoints et déterminisme.

## Matrice de non-régression

- lancement sans option strictement inchangé ;
- même graine et mêmes commandes : même simulation avec ou sans archive ;
- enregistreur et lecteur ne consomment aucun tirage aléatoire ;
- reprise `.chart` continue de fonctionner indépendamment des archives ;
- une archive hostile ne peut ni sortir du répertoire temporaire ni épuiser les
  limites configurées ;
- les trois locales gardent les mêmes clés et placeholders ;
- lecture glyphes et sprites produit les mêmes clés visibles qu'en direct ;
- fermeture interrompue laisse soit l'ancienne archive valide, soit un fichier
  temporaire explicitement non ouvrable.

## Critères de sortie

- une histoire de 1 200 cycles est partageable sans `pickle` ;
- l'utilisateur peut atteindre une date et comprendre les changements majeurs ;
- aucune relecture ne modifie le moteur ni le PRNG ;
- les limites d'entrée sont testées avant exposition dans le navigateur ;
- les budgets validés au lot 17.0 sont respectés ou révisés avec mesures ;
- les modes terminal, web direct et reprise historique restent compatibles.
