import requests

from config import (
    BASE_URL,
    API_TIMEOUT_CHAT_SEC,
    API_TIMEOUT_SPEAK_SEC,
    API_TIMEOUT_NOTE_SEC,
    API_TIMEOUT_SUGGEST_SEC,
    API_TIMEOUT_TRANSCRIBE_SEC,
    API_TIMEOUT_RELOAD_SEC,
)


def chat(event, sender=None, interaction_data=None):
    payload = {
        "event": event
    }

    if sender:
        payload["sender"] = sender

    if interaction_data:
        payload.update(interaction_data)

    response = requests.post(
        f"{BASE_URL}/chat",
        json=payload,
        timeout=API_TIMEOUT_CHAT_SEC
    )
    return response.json()


def speak(text):
    response = requests.post(
        f"{BASE_URL}/speak",
        json={"text": text},
        timeout=API_TIMEOUT_SPEAK_SEC
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
        timeout=API_TIMEOUT_NOTE_SEC
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


def delete_note(note_index):
    response = requests.delete(
        f"{BASE_URL}/notes/{note_index}",
        timeout=API_TIMEOUT_NOTE_SEC
    )
    return response.json()


def update_note(note_index, note, category=None):
    payload = {
        "note": note
    }

    if category:
        payload["category"] = category

    response = requests.put(
        f"{BASE_URL}/notes/{note_index}",
        json=payload,
        timeout=API_TIMEOUT_NOTE_SEC
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
        timeout=API_TIMEOUT_SUGGEST_SEC
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
            timeout=API_TIMEOUT_TRANSCRIBE_SEC
        )

    return response.json()


def get_model_profiles():
    response = requests.get(
        f"{BASE_URL}/model_profiles",
        timeout=API_TIMEOUT_RELOAD_SEC
    )
    return response.json()


def set_active_model_profile(profile_key):
    response = requests.post(
        f"{BASE_URL}/model_profiles/active",
        json={"profile_key": profile_key},
        timeout=API_TIMEOUT_RELOAD_SEC
    )
    return response.json()


def reload_personality():
    response = requests.post(
        f"{BASE_URL}/reload_personality",
        timeout=API_TIMEOUT_RELOAD_SEC
    )
    return response.json()
