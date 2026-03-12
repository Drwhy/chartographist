def render_logs(width, stats):
    """
    Displays the most recent event messages below the world map.
    Limited to the last 5 logs to maintain UI stability.
    """
    # Header separator proportional to map width
    print("=" * (width * 2))

    logs = stats.get('logs', [])

    # Iterate through the 5 most recent entries
    for log_entry in logs[-5:]:
        # Truncate string to fit within terminal width to prevent line wrapping
        # Calculation: (width * 2) accounts for 2-character tiles, -4 for the " > " prefix
        clean_log = str(log_entry)[:width * 2 - 4]

        # Output with left justification to clear any previous frame artifacts
        print(f" > {clean_log}".ljust(width * 2))