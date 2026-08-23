# Roadmap d’émergence de Chartographist

Ce document transforme l’analyse approfondie du projet en plan d’implémentation. Il prolonge les phases 0 à 7 déjà réalisées et devient la feuille de route des phases 8 à 15.

Les règles de [`AGENTS.md`](AGENTS.md) restent impératives : prévention des régressions, TDD strict test-first, déterminisme via `RandomService`, i18n fr/en/es et mise à jour de [`REFERENTIEL_PROJET.md`](REFERENTIEL_PROJET.md) après toute évolution structurante.

## Vision

Le but n’est pas d’accumuler des événements scriptés. Le but est d’obtenir des histoires que le moteur n’a pas écrites explicitement : famines causées par un sol épuisé, migrations qui déplacent une religion, routes commerciales devenues enjeux militaires, lignées qui accèdent au pouvoir, ruines dont les objets racontent une crise ancienne.

Une fonctionnalité contribue à l’émergence si elle relie plusieurs systèmes par une boucle causale persistante :

```text
état du monde → perception imparfaite → décision → coût/transfert
               → conséquence locale → mémoire/histoire → nouvelle décision
```

Chaque nouvelle règle doit répondre à quatre questions :

1. Quelle quantité, information ou relation est conservée ?
2. Qui peut la percevoir, et avec quelle incertitude ?
3. Quelles décisions différentes peut-elle provoquer ?
4. Quelle trace durable permet d’expliquer le résultat ?

## Principes architecturaux transversaux

### Compatibilité

- Chaque nouveau système est activé par une section de configuration explicite.
- Un ancien template sans cette section conserve le comportement historique.
- Les anciennes sauvegardes sont migrées paresseusement avec des valeurs neutres.
- Les contrats publics de `world`, `stats` et `SimulationEngine` ne sont retirés qu’après une migration documentée.

### TDD et validation

Pour chaque lot fonctionnel :

1. écrire un test de caractérisation du comportement historique concerné ;
2. écrire le test rouge du nouveau contrat ;
3. observer l’échec pour la raison attendue ;
4. implémenter le changement minimal ;
5. exécuter les tests ciblés ;
6. exécuter la suite complète ;
7. lancer des simulations multi-graines et contrôler les invariants ;
8. mettre à jour les trois locales et la documentation.

### Déterminisme

- Tous les tirages passent par [`core/random_service.py`](core/random_service.py).
- Les agrégations dont l’ordre influence une décision sont triées par identifiant stable.
- Les simulations interrompues/reprises doivent rester identiques aux simulations continues.
- Les outils d’analyse ne doivent pas consommer le PRNG de la simulation.

### Échelle de simulation

Le projet doit rester hiérarchique :

- les colonies et cohortes portent les calculs de masse ;
- les personnages importants conservent une simulation individuelle complète ;
- un individu ordinaire peut être promu en personnage notable lorsqu’un événement le rend historiquement pertinent ;
- les recherches spatiales utilisent des index, jamais un scan global lorsque la population augmente.

### Définition de « terminé » pour une phase

Une phase est terminée lorsque :

- les contrats headless sont accessibles sans rendu terminal ;
- les nouveaux états sont sérialisables et migrent depuis un monde ancien ;
- les textes visibles existent dans les trois locales avec parité de placeholders ;
- les tests couvrent nominal, limites, contrats inter-modules et reprise déterministe ;
- au moins 20 graines courtes et 3 graines longues respectent les invariants de la phase ;
- une comparaison avant/après mesure l’effet réel du système ;
- `REFERENTIEL_PROJET.md` décrit les nouveaux propriétaires et flux.

## Dépendances des phases

```mermaid
flowchart LR
    P8["Phase 8 — Observatoire et équilibre"] --> P9["Phase 9 — Ressources spatiales"]
    P9 --> P10["Phase 10 — Besoins et mémoire"]
    P9 --> P11["Phase 11 — Production et inventaires"]
    P10 --> P12["Phase 12 — Information et rumeurs"]
    P11 --> P13["Phase 13 — Factions et institutions"]
    P12 --> P13
    P13 --> P14["Phase 14 — Territoires et migrations"]
    P14 --> P15["Phase 15 — Histoire profonde et légendes"]
    P10 --> P15
```

---

# Phase 8 — Observatoire et équilibrage systémique

> État : terminée le 23 août 2026. Validation : 182 tests, campagne courte 3 × 120 cycles et campagne longue 3 × 1 200 cycles sans extinction.

## Intention d’émergence

Rendre visibles les boucles actives, dormantes ou dominantes avant de modifier l’équilibre. Cette phase doit empêcher qu’un système apparemment riche reste sans effet réel pendant des milliers de cycles.

## Problèmes actuels ciblés

- Le placement initial peut créer zéro civilisation.
- La nourriture reste souvent au plafond.
- La trésorerie et la diplomatie évoluent peu.
- La reproduction animale peut dépasser `max_fauna`.
- Les tests valident surtout des unités, moins les distributions sur plusieurs graines.

## Nouveaux contrats proposés

- `world['metrics']` : compteurs sérialisables de flux et d’états.
- `SimulationEngine.get_metrics_snapshot()` : copie défensive.
- `SimulationEngine.run_observed(cycles, sample_every)` : séries temporelles sans consommation du PRNG.
- Un outil batch séparé produit JSON/CSV de comparaison entre graines.
- Des codes explicites décrivent un échec d’initialisation du monde.

## Plan d’implémentation

### Lot 8.1 — Caractérisation et observatoire

1. Ajouter `tests/test_simulation_metrics.py`.
2. Caractériser production/consommation alimentaire, population, colonies, faune, trésorerie, prix, transactions, statuts diplomatiques, naissances et décès.
3. Créer `core/simulation_metrics.py` avec des compteurs de flux qui n’altèrent aucun système.
4. Brancher les producteurs existants : travail, alimentation, naissance, mort, commerce, raid, chasse, événement climatique.
5. Exposer des snapshots défensifs et des séries temporelles.

### Lot 8.2 — Banc multi-graines

1. Créer un runner headless sous `tools/` ou `scripts/`.
2. Séparer métriques de simulation et présentation du rapport.
3. Ajouter des profils : 120 cycles, 1 200 cycles, reprise à mi-parcours.
4. Calculer médiane, dispersion, taux d’extinction, diversité culturelle et fréquence d’utilisation des systèmes.
5. Ajouter un test garantissant que l’observation ne modifie pas l’état du PRNG.

### Lot 8.3 — Amorçage garanti

1. Écrire un test rouge sur un corpus fixe de graines problématiques.
2. Séparer recherche de sites habitables et instanciation des cités.
3. Classer les tuiles candidates par habitabilité au lieu de limiter le démarrage à 100 tirages aveugles.
4. Préserver le placement historique lorsque celui-ci réussit ; utiliser le classement comme repli déterministe.
5. Enregistrer une chronique système si le nombre demandé de cités ne peut réellement pas être placé.

### Lot 8.4 — Budget démographique de la faune

1. Distinguer capacité mondiale, capacité par biome et capacité par espèce.
2. Inclure naissances et apparitions dans le même budget.
3. Empêcher la reproduction lorsque l’habitat ne peut plus nourrir un nouvel individu.
4. Préserver le comportement historique quand `ecology.population_limits.enabled` est absent.
5. Tester absence de croissance exponentielle et reprise déterministe.

### Lot 8.5 — Rééquilibrage alimentaire minimal

1. Mesurer séparément nourriture créée, consommée, importée, pillée et perdue.
2. Retirer l’autosuffisance implicite du travail générique uniquement dans le nouveau mode d’équilibre.
3. Introduire coûts de conservation et pertes bornées.
4. Faire dépendre la spécialisation de ratios et tendances, pas seulement d’un seuil instantané.
5. Calibrer sur des distributions, sans imposer qu’une graine particulière survive.

## Fichiers principaux

- [`core/simulation_engine.py`](core/simulation_engine.py)
- [`core/world_factory.py`](core/world_factory.py)
- [`entities/spawn_system.py`](entities/spawn_system.py)
- [`entities/constructs/city.py`](entities/constructs/city.py)
- [`entities/constructs/village.py`](entities/constructs/village.py)
- [`entities/species/animal/base.py`](entities/species/animal/base.py)
- [`core/economy.py`](core/economy.py)
- [`core/persistence.py`](core/persistence.py)

## Critères de sortie

- Le nombre de cités initiales est déterministe et explicable sur le corpus de graines.
- La faune respecte une capacité documentée, reproduction comprise.
- Les flux alimentaires se réconcilient dans les métriques.
- Le banc multi-graines détecte extinction, saturation et systèmes jamais activés.
- Une observation activée ou non produit exactement le même monde.

---

# Phase 9 — Ressources spatiales et écologie renouvelable

> État : terminée en mode opt-in le 23 août 2026. Validation : 209 tests, 3 × 120 cycles actifs sans extinction, puis 3 × 1 200 cycles actifs. Une extinction tardive, causée par la divergence du flux aléatoire faunique plutôt que par un stock local nul, maintient `resources.enabled` à `false` dans le template de référence pour éviter toute régression du mode standard.

## Intention d’émergence

Transformer le terrain en acteur causal. Une tuile doit pouvoir être fertile, surexploitée, incendiée, recolonisée ou rendue stratégique par ce qu’elle contient.

## Modèle proposé

`world['resources']` contient des grilles NumPy ou structures compactes :

- `biomass` ;
- `soil_fertility` ;
- `surface_water` ;
- `fish_stock` ;
- `forest_cover` ;
- ultérieurement `stone` et `ore`.

Chaque valeur possède capacité, stock courant et taux de régénération.

## Plan d’implémentation

### Lot 9.1 — Service de ressources headless

1. Écrire les tests de forme, bornes, déterminisme et migration.
2. Créer `core/resources.py` et `ResourceSystem`.
3. Générer les capacités depuis relief, rivières, climat et biome.
4. Initialiser explicitement le stockage dans `world_factory`.
5. Exposer `get_tile_resources(x, y)` et un résumé mondial.

### Lot 9.2 — Régénération

1. Définir une cadence saisonnière.
2. Faire dépendre la régénération de température, humidité et fertilité.
3. Ajouter mortalité hivernale, sécheresse et récupération après crise.
4. Borner chaque stock et garantir l’absence de valeurs non finies.

### Lot 9.3 — Consommation écologique

1. Faire consommer de la biomasse aux herbivores.
2. Faire dépendre leur énergie du prélèvement réellement obtenu.
3. Lier reproduction animale à énergie, habitat et capacité locale.
4. Faire diminuer les populations lorsque la nourriture manque.
5. Ajouter migration animale vers des habitats voisins plus favorables.

### Lot 9.4 — Agriculture et pêche

1. Les fermiers prélèvent un rendement produit par fertilité, eau, saison et travail.
2. Les récoltes réduisent temporairement la fertilité ; repos et crues peuvent la restaurer.
3. Les pêcheurs prélèvent `fish_stock`, qui se régénère selon habitat et saison.
4. Ajouter surexploitation et effondrement local des stocks.
5. Conserver les anciennes formules lorsque le système est désactivé.

### Lot 9.5 — Perturbations persistantes

1. Les volcans brûlent biomasse et forêt et modifient localement le sol.
2. Les crues déplacent eau/fertilité au lieu d’être une simple anomalie globale.
3. Les incendies se propagent selon végétation et humidité.
4. Les terres abandonnées se réensauvagent progressivement.

## Tests structurants

- Conservation des prélèvements : gain d’un consommateur ≤ ressource retirée.
- Régénération bornée par la capacité.
- Surpâturage → baisse de biomasse → baisse d’énergie → baisse de population.
- Deux biomes produisent des trajectoires écologiques différentes.
- Reprise de checkpoint identique au cycle près.

## Critères de sortie

- La nourriture ne peut plus être créée sans source spatiale dans le mode actif.
- Une sécheresse peut provoquer une chaîne mesurable jusqu’à la population.
- Une région surexploitée récupère ou change durablement d’usage.
- Prédateurs et proies forment des cycles plutôt qu’une croissance illimitée.

---

# Phase 10 — Besoins, compétences, mémoire et personnages notables

> État : socle terminé en mode opt-in le 23 août 2026. Validation : 233 tests, 20 × 120 cycles actifs sans extinction, puis 3 × 1 200 cycles actifs. La graine 47 s’éteint uniquement en mode personnages actif et le coût long passe d’environ 0,7–0,9 s à 2,9–10,2 s selon la population ; `characters.enabled` reste donc à `false` dans le template de référence pendant la calibration.

## Intention d’émergence

Faire décider les agents depuis leur situation personnelle plutôt que depuis leur classe seule, tout en maintenant une échelle de calcul viable.

## Modèle proposé

Un personnage notable possède :

- besoins : faim, sécurité, appartenance, statut, foi, richesse ;
- compétences : agriculture, chasse, commerce, combat, soin, commandement ;
- traits : prudence, ambition, empathie, avidité, ferveur ;
- relations personnelles : affection, confiance, dette, peur, grief ;
- mémoire bornée d’événements vécus ou appris.

## Plan d’implémentation

### Lot 10.1 — Cohortes et notabilité

1. Mesurer le coût actuel des citoyens individuels.
2. Introduire un contrat `PopulationCohort` pour les habitants ordinaires sans supprimer immédiatement les citoyens existants.
3. Définir les événements de promotion en notable : accession à un rôle, victoire, découverte, crime, mariage politique, survie à une catastrophe.
4. Garantir un `entity_id` stable lors de la promotion.
5. Archiver les notables morts ou redevenus secondaires sans perdre leur histoire.

### Lot 10.2 — Besoins et compétences

1. Créer `core/needs.py` et `core/skills.py` avec valeurs bornées.
2. Ajouter évolution mensuelle et effets des actions.
3. Faire progresser les compétences par pratique, avec rendements décroissants.
4. Migrer progressivement Farmer/Hunter/Trader/Soldier vers des rôles basés sur compétences.

### Lot 10.3 — Décision par utilité

1. Définir des actions candidates avec préconditions, coût, risque et satisfaction attendue.
2. Calculer un score déterministe, le bruit éventuel passant par `RandomService`.
3. Exposer en inspection les trois meilleures options et la raison du choix.
4. Conserver les IA historiques derrière un adaptateur lorsque le système est désactivé.

### Lot 10.4 — Mémoire personnelle

1. Créer des faits structurés : témoin, cible, lieu, cycle, intensité, fiabilité.
2. Ajouter oubli, renforcement et généralisation en opinion.
3. Relier raids, famines, sauvetages, commerces et conversions aux mémoires.
4. Déduire confiance, peur et grief depuis ces faits plutôt que par mutation opaque.

### Lot 10.5 — Familles et héritage

1. Étendre les liens familiaux aux ménages.
2. Transmettre nom, patrimoine, foi, réputation et certains traits.
3. Ajouter deuil, rivalité successorale et solidarité familiale.
4. Générer les chroniques depuis les conséquences significatives, pas chaque micro-action.

## Contraintes de performance

- Mémoire bornée et indexée par importance.
- Pas de comparaison de chaque individu avec toute la population.
- Relations détaillées uniquement entre notables ou membres d’un même ménage.
- Décisions coûteuses distribuées sur plusieurs cadences.

## Critères de sortie

- Deux agents de même métier peuvent agir différemment dans la même situation.
- Une expérience passée modifie une décision future de manière inspectable.
- Un personnage peut devenir notable par ce qui lui arrive.
- Les populations importantes restent simulables grâce aux cohortes.

## Résultat du socle livré

- `core/characters.py` possède l’état personnel versionné, les décisions par utilité, les cohortes et le cycle de vie des notables ; `core/needs.py`, `core/skills.py` et `core/memory.py` isolent les règles bornées.
- Les choix expliquent leurs trois meilleurs scores, n’utilisent aucun hasard implicite et sont distribués sur trois cadences selon l’`entity_id`.
- Le commerce et les raids alimentent des mémoires vécues ; peur et grief issus d’un raid peuvent modifier une décision future.
- Les promotions de métier conservent identité, famille, compétences et souvenirs. Les enfants héritent de traits moyens et d’une part bornée des compétences parentales.
- `world['notables']` et `world['notable_archive']` sont sérialisables ; l’archive est idempotente et conserve un instantané défensif complet.
- Inspection, cohortes et métriques exposent décisions, repos, promotions, archives et état courant sans consommer le PRNG.
- Les 20 graines courtes actives terminent avec 2–3 colonies et 19–72 habitants. Sur les trois graines longues, les populations finales sont 3, 53 et 0 ; la graine 47 témoin conserve 60 habitants avec le système désactivé.
- Les producteurs de mémoire pour sauvetages, conversions et catastrophes restent à brancher lors des phases information/institutions ; le schéma les accepte déjà sans nouveau format.

---

# Phase 11 — Production, inventaires, métiers et marchés

> État : socle 11.1–11.4 et premier incrément 11.5 livrés en mode opt-in le 23 août 2026 ; entretien, dommages, transport et spécialisations régionales restent ouverts. Validation : 265 tests et 20 × 120 cycles combinés sans extinction. Sur 1 200 cycles combinés, la graine 11 survit mais les graines 29 et 47 s’éteignent alors que leurs témoins désactivés survivent ; le mode reste donc désactivé par défaut.


## Intention d’émergence

Faire naître les métiers, échanges et crises depuis des chaînes de production et besoins matériels réels.

## Modèle proposé

- Définitions data-driven de ressources et objets.
- Inventaires personnels légers et stockages de colonies.
- Recettes avec entrées, outils, compétence, temps et sorties.
- Ordres de travail issus des pénuries et priorités collectives.
- Prix formés par stock, demande récente, coût et accessibilité.

## Plan d’implémentation

### Lot 11.1 — Catalogue matériel

1. Définir les schémas `resources`, `items` et `recipes` dans le template/modding.
2. Valider IDs, références, cycles et quantités positives.
3. Créer `core/materials.py` et des snapshots immuables.
4. Ajouter tests de mods qui étendent matériaux et recettes sans conflit.

### Lot 11.2 — Stockages et conservation

1. Ajouter `stockpile` aux colonies avec migration vide.
2. Centraliser tous les transferts dans un service transactionnel.
3. Interdire stocks négatifs et duplication d’objets.
4. Ajouter capacité, détérioration et pertes selon le type de bien.

### Lot 11.3 — Production

1. Construire des ordres depuis besoins alimentaires, construction, défense et commerce.
2. Affecter la main-d’œuvre selon compétences, urgence et préférences.
3. Consommer ressources, temps et outils avant de produire.
4. Gérer échec partiel, qualité et sous-produits.

### Lot 11.4 — Marchés multi-biens

1. Généraliser `TradeTransaction` à plusieurs marchandises.
2. Faire choisir les routes selon prix, risque, distance et capacité.
3. Ajouter coût de transport, péages et pertes.
4. Laisser apparaître arbitrage, pénuries régionales et spécialisations.
5. Maintenir la conservation exacte des biens et de la monnaie.

### Lot 11.5 — Infrastructures

1. Routes, greniers, marchés, ateliers et fortifications deviennent des constructions avec coût et entretien.
2. Leur état modifie transport, pertes, défense et capacité.
3. Les catastrophes peuvent les endommager ; la réparation concurrence les autres ordres.

## Critères de sortie

- Une ville ne produit pas sans ressources, travail et outils requis.
- Une pénurie crée une chaîne de décisions observable.
- Des régions différentes développent des spécialisations différentes.
- Les prix influencent réellement les routes commerciales.

## État d’implémentation du socle

- Le catalogue, les stockages conservateurs, la détérioration, les ordres déterministes et leur persistance sont opérationnels.
- La chaîne nourriture brute → travail outillé → ration → consommation fonctionne réellement et reste compatible avec le stock alimentaire historique.
- Les transactions multi-biens conservent monnaie et marchandises ; les prix, la distance et le risque influencent le classement déterministe des marchés.
- Un ordre irréalisable ne bloque plus les recettes réalisables, ce qui protège la production alimentaire d’une famine de file.
- Le bois est prélevé de manière conservatrice dans la forêt locale, sous plancher écologique, puis transformé en planches par un travailleur compétent.
- Le premier ordre d’infrastructure produit un kit de grenier : son installation persistante et idempotente augmente la capacité de stockage de 250 par niveau, jusqu’à deux niveaux, sans produire de kit après saturation.
- Inspection et métriques rendent visibles stocks, capacités, ordres, production, pertes et échanges.
- Les critères « préconditions de production », « pénurie observable » et « prix influençant les routes » disposent d’un socle testable. Le critère de spécialisations régionales n’est pas encore satisfait.
- Restent à livrer : durabilité des outils, qualité/sous-produits, coût/péages/pertes de transport, entretien, dommages, autres infrastructures et arbitrage régional. Le mode demeure désactivé par défaut pendant ce travail, le recalibrage démographique et le profilage.


---

# Phase 12 — Information locale, exploration et rumeurs

## Intention d’émergence

Supprimer l’omniscience. Faire de l’information une ressource qui voyage, vieillit, se déforme et influence les décisions.

## Plan d’implémentation

### Lot 12.1 — Graphe de connaissances

1. Créer `core/knowledge.py`.
2. Stocker pour chaque colonie/notable des faits avec source, cycle, fiabilité et position estimée.
3. Migrer `known_cities` vers des connaissances structurées.
4. Remplacer les appels globaux de `DiscoveryService` dans le nouveau mode.

### Lot 12.2 — Observation et cartographie

1. Ajouter rayon de perception et découvertes de terrain/sites/ressources.
2. Les explorateurs construisent des cartes partielles.
3. Les cartes peuvent être copiées, vendues, volées ou devenir obsolètes.
4. L’inspection distingue fait mondial et connaissance de l’agent.

### Lot 12.3 — Propagation des nouvelles

1. Commerce, migration, armées et pèlerinages transportent des faits.
2. La fiabilité diminue avec nombre de transmissions, distance et temps.
3. Traits et relations influencent croyance et déformation.
4. Une correction peut concurrencer une ancienne rumeur.

### Lot 12.4 — Décisions sous information imparfaite

1. Les marchands évaluuent marchés connus, pas prix mondiaux exacts.
2. Les villes réagissent aux menaces rapportées.
3. Les migrants choisissent depuis réputation et rumeurs.
4. Les erreurs d’information peuvent créer expéditions inutiles ou conflits.

## Critères de sortie

- Une colonie isolée ignore réellement une ville distante.
- Une route commerciale accélère aussi la diffusion d’informations et religions.
- Deux communautés peuvent croire des versions différentes d’un même événement.
- Toute décision basée sur une rumeur expose sa source et sa fiabilité.

---

# Phase 13 — Factions, institutions et politique

## Intention d’émergence

Faire de la colonie un ensemble d’intérêts concurrents, pas un acteur homogène.

## Modèle proposé

- factions : familles, métiers, religions, militaires, marchands ;
- institutions : conseil, chefferie, monarchie, temple, guildes ;
- offices détenus par des notables ;
- légitimité, influence, ressources et revendications ;
- politiques qui modifient réellement taxes, travail, commerce, religion et guerre.

## Plan d’implémentation

### Lot 13.1 — Registre de factions

1. Créer `core/factions.py` avec IDs stables et stockage dans `world` ou la colonie.
2. Déduire l’adhésion depuis ménage, métier, foi et relations.
3. Ajouter influence, satisfaction et objectifs bornés.
4. Exposer inspection et chroniques liées.

### Lot 13.2 — Institutions et offices

1. Définir les formes de gouvernement data-driven.
2. Créer offices, règles d’éligibilité, durée et succession.
3. Nommer des notables sans créer de doublon d’identité.
4. Ajouter vacance, régence et crise successorale.

### Lot 13.3 — Décisions collectives

1. Les politiques deviennent des propositions avec partisans/opposants.
2. Calculer soutien depuis intérêts, relations, légitimité et information.
3. Appliquer les politiques via des modificateurs explicites et temporisés.
4. Journaliser causes, vote/décision et groupes affectés.

### Lot 13.4 — Conflits internes

1. Accumuler mécontentement par faim, pertes, discrimination, taxes et défaites.
2. Produire protestation, sabotage, sécession ou révolte selon capacités réelles.
3. Permettre négociation, répression et réforme.
4. Relier guerre civile à territoire et migrations de la phase suivante.

## Critères de sortie

- Deux factions d’une même ville poursuivent des objectifs incompatibles.
- Une succession dépend des personnes et règles existantes.
- Une famine peut provoquer réforme, coup d’État ou exode selon le contexte.
- Les politiques ont des gagnants, perdants et conséquences mesurables.

---

# Phase 14 — Territoires, logistique, migrations et guerre causale

## Intention d’émergence

Donner une géographie réelle au pouvoir. Une guerre doit découler d’enjeux et dépendre de routes, ravitaillement, saison, information et soutien politique.

## Plan d’implémentation

### Lot 14.1 — Revendications territoriales

1. Créer une couche de contrôle/influence par colonie ou polity.
2. Propager l’influence selon population, routes, fortifications et distance.
3. Détecter frontières et tuiles contestées.
4. Relier ressources stratégiques et griefs diplomatiques.

### Lot 14.2 — Mobilité et chemins

1. Remplacer le déplacement purement glouton par un service de chemin configurable.
2. Intégrer terrain, route, météo, danger et connaissance.
3. Mettre en cache les routes avec invalidation lorsque le monde change.
4. Mesurer le coût pour éviter une explosion algorithmique.

### Lot 14.3 — Migration

1. Calculer pressions de départ : faim, guerre, climat, persécution, opportunité.
2. Calculer attractivité depuis informations connues, liens familiaux et capacité d’accueil.
3. Déplacer cohortes et quelques notables plutôt que tous les individus séparément.
4. Transporter foi, culture, compétences, maladies et récits.
5. Ajouter intégration, diaspora, discrimination et retours.

### Lot 14.4 — Guerre et logistique

1. Remplacer la probabilité brute par des objectifs de guerre : ressource, frontière, vengeance, religion, succession.
2. Créer armées/cohortes avec vivres, moral et commandement.
3. Le ravitaillement dépend des routes, stocks, saisons et raids.
4. Les pertes affectent familles, factions, économie et légitimité.
5. Ajouter occupation, siège, retraite, prisonniers et traité.

### Lot 14.5 — Paix et conséquences

1. Les traités transfèrent territoire, tribut, otages ou droits commerciaux.
2. Les griefs diminuent ou persistent selon le règlement.
3. Ruines, vétérans, réfugiés et dettes continuent d’influencer le monde.
4. La diplomatie résume ces causes sans perdre son adaptateur historique.

## Critères de sortie

- Une guerre possède une cause, un objectif, un coût et une fin explicables.
- Une armée isolée peut échouer malgré sa supériorité numérique.
- Une migration modifie durablement culture, économie et politique des régions traversées.
- Les frontières répondent aux routes, populations et ressources.

---

# Phase 15 — Histoire profonde, objets, sites et légendes

## Intention d’émergence

Rendre les chaînes causales lisibles et mémorables. L’histoire ne doit pas seulement être un journal de chaînes, mais un graphe de faits, acteurs, objets, lieux et conséquences.

## Plan d’implémentation

### Lot 15.1 — Événements causaux structurés

1. Étendre les chroniques avec `event_type`, acteurs, objets, lieux, causes et conséquences.
2. Conserver `message` pour compatibilité terminal et sauvegardes existantes.
3. Introduire des liens `caused_by` et `resulted_in` bornés.
4. Produire le texte par i18n depuis les faits structurés lorsque possible.

### Lot 15.2 — Sites persistants

1. Donner une identité aux champs de bataille, ruines, sanctuaires, mines et routes remarquables.
2. Stocker fondation, propriétaires, destructions et reconstructions.
3. Faire évoluer l’apparence et les ressources selon l’histoire du site.
4. Permettre redécouverte et réoccupation.

### Lot 15.3 — Objets et artefacts

1. Promouvoir certains objets en artefacts selon qualité, propriétaire et événements vécus.
2. Conserver créateur, matériau, inscriptions, détenteurs et lieux.
3. Faire circuler les artefacts par héritage, commerce, pillage, don et perte.
4. Leur réputation influence prestige, revendications et pèlerinages.

### Lot 15.4 — Réputation et légendes

1. Distinguer faits réels, connaissances et récits publics.
2. Calculer renommée depuis propagation et importance, pas depuis un score arbitraire isolé.
3. Faire varier les versions d’une légende selon culture et faction.
4. Permettre qu’une légende motive exploration, guerre ou culte.

### Lot 15.5 — Interface « Pourquoi ? »

1. Ajouter requêtes headless par entité, lieu, objet, famille et événement.
2. Construire une vue chronologique et une vue causale.
3. Pour une situation actuelle, exposer les principales causes : « pourquoi cette ville a faim ? », « pourquoi cette guerre ? ».
4. Ajouter filtres terminal et exports structurés pour outils futurs.

## Critères de sortie

- Une situation importante peut être expliquée par une chaîne causale traversant plusieurs systèmes.
- Les ruines et artefacts conservent leur histoire après disparition de leurs créateurs.
- Deux cultures peuvent raconter différemment le même fait.
- Le joueur peut découvrir une histoire sans que celle-ci ait été écrite comme scénario prédéfini.

---

# Ordre de réalisation recommandé à l’intérieur de chaque phase

Pour réduire le risque, chaque phase suit le même découpage :

1. **Contrats et caractérisation** — tests du comportement actuel et schéma des nouveaux états.
2. **Service headless pur** — calculs sans terminal ni mutation externe implicite.
3. **Intégration minimale** — un producteur et un consommateur réels.
4. **Persistance et migration** — checkpoint courant et monde ancien.
5. **Inspection et métriques** — expliquer l’état avant d’étendre les effets.
6. **Extension data-driven** — template, scénario et mods.
7. **Interface et i18n** — textes fr/en/es et navigation.
8. **Validation émergente** — tests multi-graines, simulations longues et comparaison statistique.

# Prochaine étape : terminer la phase 11

Le socle matériel est disponible en mode opt-in. Le prochain incrément doit fermer les boucles encore dormantes avant d’ouvrir la phase 12 :

1. ajouter l’entretien et les dommages au grenier existant, avec ordres de réparation concurrents et migration de l’état ;
2. faire construire atelier, marché, route et fortification depuis des ordres concurrents, puis brancher leurs effets sur production, transport et défense ;
3. compléter coûts, pertes et péages de transport pour que l’arbitrage multi-biens choisisse des routes réellement différentes ;
4. ajouter durabilité des outils, qualité et sous-produits sans rompre la conservation des biens ;
5. recalibrer la boucle ressources–matériaux sur les graines longues, profiler, puis n’activer les modes par défaut qu’après survie comparable des témoins et satisfaction du critère de spécialisation régionale.
