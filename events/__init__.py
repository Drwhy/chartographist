import os
import importlib

# On liste tous les fichiers .py dans ce dossier (sauf __init__, base, registry et manager)
pkg_dir = os.path.dirname(__file__)
for file in os.listdir(pkg_dir):
    if file.endswith(".py") and file not in ["__init__.py", "base_event.py", "registry.py", "manager.py"]:
        module_name = f"events.{file[:-3]}"
        importlib.import_module(module_name)