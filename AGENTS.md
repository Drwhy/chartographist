# Directives de développement

Ces règles s'appliquent à toute modification de ce dépôt.

## Priorité absolue : éviter les régressions

- Préserver les comportements, contrats de données et interfaces existants sauf demande explicite contraire.
- Avant de modifier un système, identifier ses appelants, ses consommateurs et les clés de configuration ou d'état partagé concernées.
- Maintenir le déterminisme : toute décision aléatoire de simulation doit passer par `core.random_service.RandomService`.
- Préférer les changements ciblés, rétrocompatibles et dotés de valeurs par défaut pour les nouvelles options.
- Ne pas masquer une erreur ou supprimer un comportement existant uniquement pour faire passer un test.
- Exécuter les tests existants avant et après une modification lorsque cela est possible.

## Internationalisation obligatoire

- Aucun nouveau texte visible par l'utilisateur ne doit être codé en dur dans le code Python.
- Ajouter chaque nouveau texte aux trois catalogues existants : `locales/textes.fr.json`, `locales/textes.en.json` et `locales/textes.es.json`.
- Conserver exactement les mêmes chemins de clés dans les trois fichiers.
- Accéder aux textes avec `core.translator.Translator.translate(...)`.
- Si les besoins dépassent les capacités actuelles, étendre `Translator` et son format de catalogue au lieu de créer un second mécanisme i18n.
- Ajouter des tests vérifiant la parité des clés entre locales, le chargement et le formatage des nouvelles traductions.

## Tests obligatoires

- Toute modification fonctionnelle doit être accompagnée de tests automatisés nouveaux ou adaptés couvrant le comportement nominal et les cas limites pertinents.
- Toute correction de bug doit inclure un test de non-régression qui échoue sans la correction.
- Tester les contrats affectés entre modules, pas seulement les fonctions isolées.
- Les changements de configuration ou de locales doivent avoir une validation automatisée de structure et de cohérence.
- Les changements exclusivement documentaires doivent au minimum faire l'objet de vérifications automatisées adaptées : liens locaux, format ou commandes documentées si elles sont exécutables.
- Utiliser de préférence la bibliothèque standard `unittest` tant qu'aucun autre framework de test n'est adopté par le projet.
- Placer les tests dans `tests/` en reproduisant autant que possible l'organisation des modules testés.
- Ne considérer une tâche terminée qu'après exécution réussie des tests concernés et d'une vérification de non-régression proportionnée au changement.

## Référence d'architecture

Consulter `REFERENTIEL_PROJET.md` avant une modification transversale. Mettre ce référentiel à jour lorsque des fichiers, responsabilités, contrats `world`/`stats`, flux d'initialisation ou procédures de test changent.
