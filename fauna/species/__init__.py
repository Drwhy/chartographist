# Import des classes spécialisées depuis leurs fichiers respectifs
from .flyer import Flyer
from .aquatic import Aquatic

# Import des classes de prédateurs depuis le sous-package predator
# Grâce au __init__.py dans le dossier predator, on peut les importer ainsi :
from .predator import Predator, Wolf, Bear
