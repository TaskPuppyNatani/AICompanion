from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "speech_data"

PERSONALITY_FILE = DATA_DIR / "personality.md"

NOTES_FILE = DATA_DIR / "notes.json"

API_HOST = "192.168.1.4"
API_PORT = 5001

BASE_URL = f"http://{API_HOST}:{API_PORT}"