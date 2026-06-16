import requests

BASE_URL = "http://192.168.1.4:5001"


def chat(event, sender=None):
    payload = {
        "event": event
    }

    if sender:
        payload["sender"] = sender

    response = requests.post(
        f"{BASE_URL}/chat",
        json=payload,
        timeout=10
    )
    return response.json()


def speak(text):
    response = requests.post(
        f"{BASE_URL}/speak",
        json={"text": text},
        timeout=30
    )
    return response.content


def save_note(note, category=None):
    payload = {
        "note": note
    }

    if category:
        payload["category"] = category

    response = requests.post(
        f"{BASE_URL}/note",
        json=payload,
        timeout=10
    )
    return response.json()


def get_notes():
    response = requests.get(
        f"{BASE_URL}/notes"
    )
    return response.json()


def get_recent_notes():
    response = requests.get(
        f"{BASE_URL}/notes/recent"
    )
    return response.json()


def search_notes(query):
    response = requests.get(
        f"{BASE_URL}/notes/search",
        params={"q": query}
    )
    return response.json()


def suggest_category(note_text):
    response = requests.get(
        f"{BASE_URL}/notes/suggest-category",
        params={"q": note_text},
        timeout=10
    )
    return response.json()


def transcribe_audio(audio_path):
    with open(audio_path, "rb") as audio_file:
        response = requests.post(
            f"{BASE_URL}/notes/transcribe",
            files={
                "audio": (
                    "voice_note.wav",
                    audio_file,
                    "audio/wav"
                )
            },
            timeout=120
        )

    return response.json()

def reload_personality():
    response = requests.post(
        f"{BASE_URL}/reload_personality",
        timeout=10
    )
    return response.json()