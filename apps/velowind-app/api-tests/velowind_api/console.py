"""Small, immediately flushed progress messages; never dump payloads or config."""
from datetime import datetime


def log(event, message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    # Keep each event on one line when output is redirected to a CI log.
    message = str(message).replace("\r", " ").replace("\n", " ")
    print(f"[{timestamp}] [{event}] {message}", flush=True)
