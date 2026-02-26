# core/logger.py

class GameLogger:
    _logs = []

    @classmethod
    def log(cls, message):
        """Ajoute un message au système global."""
        cls._logs.append(message)

    @classmethod
    def get_new_logs(cls):
        """Récupère les logs et vide la file d'attente pour le prochain tour."""
        current_batch = list(cls._logs)
        cls._logs.clear()
        return current_batch