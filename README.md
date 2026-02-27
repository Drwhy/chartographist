📜 Chartographist

Chartographist est un moteur de simulation de monde procédural en Python, tournant intégralement dans le terminal. Il simule l'évolution d'un écosystème complexe où la géographie, le climat et les formes de vie (humains et animaux) interagissent de manière déterministe.
🌍 Fonctionnalités principales
🧬 Génération procédurale & Déterminisme

    Système de Seed Centralisé : Grâce au RandomService, une même seed générera exactement la même carte, les mêmes déplacements d'animaux et la même évolution de civilisation.

    Biomes Dynamiques : Calcul de la température basé sur l'altitude, la latitude et l'inclinaison axiale (saisons).

    Rendu ASCII/Emoji : Une interface visuelle riche directement dans votre console.

👥 Civilisation & Acteurs

    Expansion Intelligente : Les colons fondent des villages qui évoluent en cités selon leur population.

    Métiers spécialisés :

        🏹 Chasseurs : Protègent les villages des prédateurs terrestres.

        🎣 Pêcheurs : Opèrent dans les villages côtiers, capables d'utiliser des barques (🛶) pour traquer les poissons en mer.

    Logique de survie : Les acteurs doivent récolter des ressources pour assurer la croissance du village.

🦁 Faune & Danger

    Écosystème terrestre : Loups (rapides) et Ours (puissants et territoriaux).

    Écosystème marin :

        🐟 Poissons : Évoluent dans les eaux peu profondes.

        🦈 Requins : Prédateurs redoutables qui chassent les poissons et les pêcheurs en barque.

    Système de Combat : Basé sur un facteur de dangerosité propre à chaque espèce, avec des issues variées (Victoire, Fuite ou Mort).

🚀 Installation

    Clonez le dépôt :
    Bash

    git clone https://github.com/Drwhy/chartographist.git
    cd chartographist

    Installez les dépendances :
    Bash

    pip install -r requirements.txt

🎮 Utilisation

Lancez la simulation avec une seed spécifique pour générer un monde unique :
Bash

python main.py [votre_seed]

Si aucune seed n'est fournie, une seed aléatoire sera générée automatiquement.
Commandes (en cours de simulation) :

    Ctrl+C : Arrêter la simulation et afficher les statistiques finales.

🛠️ Structure du Projet
Plaintext

chartographist/
├── core/
│   ├── random_service.py   # Service central de déterminisme
│   ├── system.py           # Gestion des arguments et config
│   └── logger.py           # Historique des événements du monde
├── entities/
│   ├── actors/             # Humains (Settlers, Hunters, Fishermen)
│   ├── animals/            # Faune (Wolf, Bear, Fish, Shark)
│   └── constructs/         # Infrastructures (Village, Road)
├── render/
│   └── ui_map.py           # Logique d'affichage et biomes
└── main.py                 # Point d'entrée de la simulation

⚖️ Équilibrage du Combat

Le système de combat utilise la formule suivante dans Animal.py :

    Victoire : roll > (0.6 + danger / 2)

    Fuite : roll > danger

    Défaite : roll < danger

Animal	Danger	Type
🐺 Loup	0.3	Terrestre
🐻 Ours	0.8	Terrestre
🦈 Requin	0.7	Aquatique

Développé avec ❤️ par Drwhy