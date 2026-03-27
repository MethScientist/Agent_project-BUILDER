# utils/logger.py
import datetime
import sys
from config.settings import SETTINGS


def _log(message, level="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level}] {message}"
    try:
        print(entry)
    except UnicodeEncodeError:
        # Fallback for Windows consoles with cp1252: replace unsupported chars
        safe = entry.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8"
        )
        print(safe)
    with open(SETTINGS["log_file"], "a", encoding="utf-8") as f:
        f.write(entry + "\n")

def log_info(message):
    _log(message, "INFO")

def log_warning(message):
    _log(message, "WARNING")

def log_error(message):
    _log(message, "ERROR")
