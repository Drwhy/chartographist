class GameLogger:
    """
    Global static logger for capturing simulation events.
    Acts as a buffer to store messages until the UI is ready to render them.
    """
    _logs = []

    @classmethod
    def log(cls, message):
        """
        Adds a new event message to the global log queue.
        Ensures the input is converted to a string to prevent rendering crashes.
        """
        if message:
            cls._logs.append(str(message))

    @classmethod
    def get_new_logs(cls):
        """
        Retrieves all accumulated logs and flushes the queue for the next tick.
        Returns:
            list: A list of string messages from the current turn.
        """
        current_batch = list(cls._logs)
        cls._logs.clear()
        return current_batch