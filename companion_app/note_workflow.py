from companion_app import api_client


def request_category_suggestion(note_text):
    payload = api_client.suggest_category(note_text)
    return payload.get("suggestion")


def process_note_save(note_text, category=None):
    return api_client.save_note(note_text, category)


def request_transcription(audio_path):
    payload = api_client.transcribe_audio(audio_path)
    return payload.get("text", "").strip()


def finalize_note_workflow(note_text, category, should_continue):
    if not should_continue:
        return False, None

    payload = process_note_save(note_text, category)
    return True, payload
