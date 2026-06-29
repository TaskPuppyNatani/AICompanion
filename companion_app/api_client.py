import time

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


def _print_chat_response_diagnostics(url, payload, response):
    raw_content = response.content or b""
    preview = raw_content[:1000].decode("utf-8", errors="replace")

    print("[CHAT JSON TRACE] Request URL:", url)
    print("[CHAT JSON TRACE] Request payload:", payload)
    print("[CHAT JSON TRACE] Status code:", response.status_code)
    print("[CHAT JSON TRACE] Content-Type:", response.headers.get("Content-Type"))
    print("[CHAT JSON TRACE] Raw response length:", len(raw_content))
    print("[CHAT JSON TRACE] Raw response preview:", repr(preview))


def chat(event, sender=None, interaction_data=None):
    payload = {
        "event": event
    }

    if sender:
        payload["sender"] = sender

    if interaction_data:
        payload.update(interaction_data)

    url = f"{BASE_URL}/chat"
    should_log_perf = event == "click"
    start_time = time.perf_counter()
    try:
        response = requests.post(
            url,
            json=payload,
            timeout=API_TIMEOUT_CHAT_SEC
        )
    finally:
        if should_log_perf:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            print(f"[AI CLICK PERF] api_client.chat {elapsed_ms:.2f} ms")

    _print_chat_response_diagnostics(url, payload, response)

    try:
        return response.json()
    except Exception:
        print("[CHAT JSON TRACE] JSON parsing failed.")
        raise


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
