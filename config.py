from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "speech_data"

PERSONALITY_FILE = DATA_DIR / "personality.md"

NOTES_FILE = DATA_DIR / "notes.json"

API_HOST = "192.168.1.4"
API_PORT = 5001

BASE_URL = f"http://{API_HOST}:{API_PORT}"

OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434

OLLAMA_GENERATE_URL = (
    f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
)

OLLAMA_MODEL_NAME = "phi4-mini:latest"

NOTIFY_SERVER_HOST = "127.0.0.1"
NOTIFY_SERVER_PORT = 5000

SPEECH_SERVER_HOST = "0.0.0.0"
SPEECH_SERVER_PORT = 5001