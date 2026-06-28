from flask import Flask, request, send_file, jsonify
import numpy as np
import re
import soundfile as sf
import tempfile
import random
import json
import threading
from pathlib import Path
from datetime import datetime
from config import (
    SPEECH_SERVER_HOST,
    SPEECH_SERVER_PORT,
    STT_MODEL_NAME,
    STT_DEVICE,
    STT_COMPUTE_TYPE,
    STT_BEAM_SIZE,
    STT_LANGUAGE,
    TTS_LANG_CODE,
    TTS_VOICE,
    TTS_SAMPLE_RATE,
    NOTES_FILE,
    PERSONALITY_FILE,
    MEMORY_FILE,
    )

from speech_data.notes_data import NOTE_CONFIRMATIONS, CATEGORY_KEYWORDS
from speech_data.chat_data import (
    CLICK_RESPONSES,
    CLICK_MEMORY_RESPONSES,
    CLICK_MILESTONES,
    STARTUP_RESPONSES,
    DISCORD_RESPONSES,
    DISCORD_SENDER_RESPONSES,
)
from speech_data.llm_service import LLMService
from companion_app.model_profiles import (
    get_active_profile_name,
    list_model_profiles,
    set_active_model_profile,
)

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

app = Flask(__name__)

stt_model = None
stt_model_lock = threading.Lock()


class LazyComponent:
    """Thread-safe lazy initialization for reusable long-lived components.

    This helper is intentionally generic so components such as Kokoro, Whisper,
    Vision, or OCR can adopt the same pattern without component-specific logic.
    """

    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    READY = "ready"
    FAILED = "failed"

    def __init__(self, initializer):
        self.initializer = initializer
        self.state = self.NOT_INITIALIZED
        self.instance = None
        self.error = None
        self.lock = threading.Lock()

    @property
    def ready(self):
        return self.state == self.READY

    def get(self):
        if self.ready:
            return self.instance

        if self.state == self.FAILED:
            raise self.error

        with self.lock:
            if self.ready:
                return self.instance

            if self.state == self.FAILED:
                raise self.error

            self.state = self.INITIALIZING

            try:
                self.instance = self.initializer()
            except Exception as e:
                self.error = e
                self.state = self.FAILED
                raise

            self.state = self.READY
            return self.instance


def load_notes():

    if NOTES_FILE.exists():
        with open(NOTES_FILE, "r") as f:
            return json.load(f)

    return []

def save_notes(notes):

    with open(NOTES_FILE, "w") as f:
        json.dump(notes, f, indent=4)

def add_note(note_text, category=None):

    notes = load_notes()

    note_entry = {
        "note": note_text,
        "timestamp": datetime.now().isoformat()
    }

    if isinstance(category, str) and category.strip():
        note_entry["category"] = category.strip()

    notes.append(note_entry)

    save_notes(notes)


def delete_note(note_index):
    notes = load_notes()

    if not isinstance(note_index, int):
        return None

    if note_index < 0 or note_index >= len(notes):
        return None

    deleted_note = notes.pop(note_index)
    save_notes(notes)
    return deleted_note


def update_note(note_index, note_text, category=None):
    if not isinstance(note_text, str) or not note_text.strip():
        return None, "empty"

    notes = load_notes()

    if not isinstance(note_index, int):
        return None, "not_found"

    if note_index < 0 or note_index >= len(notes):
        return None, "not_found"

    existing_note = notes[note_index]

    if isinstance(existing_note, dict):
        updated_note = dict(existing_note)
    else:
        updated_note = {}

    updated_note["note"] = note_text.strip()

    if isinstance(category, str) and category.strip():
        updated_note["category"] = category.strip()
    else:
        updated_note.pop("category", None)

    notes[note_index] = updated_note
    save_notes(notes)
    return updated_note, None


def get_latest_note():
    notes = load_notes()

    if notes:
        return notes[-1]

    return None

def extract_note_text(note_entry):
    if isinstance(note_entry, dict):
        value = note_entry.get("note", "")
        return value if isinstance(value, str) else str(value)

    return str(note_entry)

def extract_note_category(note_entry):
    if isinstance(note_entry, dict):
        value = note_entry.get("category", "")
        return value if isinstance(value, str) else str(value)

    return ""

def search_notes(query):
    notes = load_notes()
    needle = query.lower()

    return [
        note for note in notes
        if needle in extract_note_text(note).lower()
    ]

def get_recent_notes(limit=5):
    notes = load_notes()
    return list(reversed(notes[-limit:]))

def filter_notes_by_category(category):
    notes = load_notes()
    needle = category.lower()

    return [
        note for note in notes
        if extract_note_category(note).lower() == needle
    ]

def suggest_category(note_text):
    if not isinstance(note_text, str):
        return None

    text = note_text.lower()
    best_category = None
    best_score = 0

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)

        if score > best_score:
            best_category = category
            best_score = score

    if best_score == 0:
        return None

    return best_category

def get_stt_model():
    global stt_model

    if WhisperModel is None:
        return None

    if stt_model is None:
        with stt_model_lock:
            if stt_model is None:
                stt_model = WhisperModel(
                    STT_MODEL_NAME,
                    device=STT_DEVICE,
                    compute_type=STT_COMPUTE_TYPE
                )

    return stt_model

def load_personality():
    if PERSONALITY_FILE.exists():
        with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
            return f.read()

    return ""

PERSONALITY = load_personality()
llm_service = LLMService()

def load_memory():
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)

    return {
        "click_count": 0,
        "startup_count": 0,
        "last_startup": "",
        "last_response": ""
    }


def save_memory(memory):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)


def create_tts_pipeline():
    from kokoro import KPipeline

    print("Loading Kokoro...")
    pipeline = KPipeline(lang_code=TTS_LANG_CODE)
    print("Kokoro ready.")
    return pipeline


tts_component = LazyComponent(create_tts_pipeline)


TTS_PROSE_FENCE_TAGS = {"", "text", "txt", "plain", "plaintext"}
TTS_CODE_FENCE_TAGS = {
    "python",
    "py",
    "json",
    "javascript",
    "js",
    "typescript",
    "ts",
    "html",
    "css",
    "bash",
    "sh",
    "powershell",
    "ps1",
    "xml",
    "yaml",
    "yml",
    "sql",
}


def normalize_fence_tag(fence_line):
    return fence_line.strip()[3:].strip().lower()


def sanitize_tts_text(text):
    lines = str(text or "").splitlines()
    sanitized_lines = []
    inside_fenced_block = False
    fence_tag = ""
    fenced_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if inside_fenced_block:
                if fence_tag in TTS_PROSE_FENCE_TAGS:
                    sanitized_lines.extend(fenced_lines)

                inside_fenced_block = False
                fence_tag = ""
                fenced_lines = []
            else:
                inside_fenced_block = True
                fence_tag = normalize_fence_tag(stripped)
                fenced_lines = []

            continue

        if inside_fenced_block:
            fenced_lines.append(line)
            continue

        if re.fullmatch(r"-{3,}", stripped):
            continue

        sanitized_lines.append(line)

    return "\n".join(sanitized_lines).strip()


def audio_segment_to_array(audio):
    if audio is None:
        return None

    if hasattr(audio, "detach"):
        audio = audio.detach().cpu().numpy()
    else:
        audio = np.asarray(audio)

    audio = np.asarray(audio).squeeze()

    if audio.size == 0:
        return None

    return audio.reshape(-1)


@app.route("/chat", methods=["POST"])
def chat():

    memory = load_memory()

    data = request.json or {}

    event = data.get("event", "click")
    sender = data.get("sender")
    if isinstance(sender, str):
        sender = sender.strip()
    else:
        sender = ""

    summary = data.get("summary")
    if isinstance(summary, str):
        summary = summary.strip()
    else:
        summary = ""

    latest_note_text_cache = None

    def get_latest_note_text_for_context():
        nonlocal latest_note_text_cache

        if latest_note_text_cache is not None:
            return latest_note_text_cache

        latest_note_entry = get_latest_note()

        if latest_note_entry is None:
            latest_note_text_cache = ""
        else:
            latest_note_text_cache = extract_note_text(latest_note_entry).strip()

        return latest_note_text_cache

    def build_llm_context(latest_note_text=None):
        resolved_latest_note = latest_note_text

        if resolved_latest_note is None:
            resolved_latest_note = get_latest_note_text_for_context()

        return llm_service.build_context(
            personality=PERSONALITY,
            latest_note=resolved_latest_note,
            click_count=memory.get("click_count", 0),
            notification={
                "source": event,
                "sender": sender,
                "summary": summary,
            },
        )

    def has_llm_text(candidate):
        return isinstance(candidate, str) and bool(candidate.strip())

    # Track usage
    if event == "click":
        memory["click_count"] += 1

    elif event == "startup":
        memory["startup_count"] += 1

    save_memory(memory)

    click_responses = CLICK_RESPONSES
    startup_responses = STARTUP_RESPONSES

    discord_responses = [
        message.format(sender=sender)
        for message in DISCORD_RESPONSES
    ]

    discord_sender_responses = [
        message.format(sender=sender)
        for message in DISCORD_SENDER_RESPONSES
    ]

    if event == "startup":

        response = random.choice(startup_responses)

    elif event == "discord":

        notification_context = build_llm_context()
        llm_notification_response = llm_service.generate_notification_response(
            notification_context
        )

        if has_llm_text(llm_notification_response):
            response = llm_notification_response.strip()
        elif sender:
            response = random.choice(discord_sender_responses)
        else:
            response = random.choice(discord_responses)

    else:
        milestone_response = None

        if event == "click":
            milestone_response = CLICK_MILESTONES.get(memory["click_count"])

        if milestone_response is not None:
            response = milestone_response

        else:
            latest_note = get_latest_note() if event == "click" else None
            latest_note_text = extract_note_text(latest_note).strip() if latest_note else ""
            latest_note_text_cache = latest_note_text

            if (
                event == "click"
                and latest_note_text
                and random.random() < 0.2
            ):
                memory_context = build_llm_context(latest_note_text=latest_note_text)
                llm_memory_response = llm_service.generate_memory_response(
                    memory_context
                )

                if has_llm_text(llm_memory_response):
                    response = llm_memory_response.strip()
                else:
                    template = random.choice(CLICK_MEMORY_RESPONSES)
                    response = template.format(note=latest_note_text)
            else:

                llm_click_response = None

                if event == "click" and random.random() < 0.75:
                    click_context = build_llm_context(
                        latest_note_text=latest_note_text or None
                    )
                    print("AI CLICK TRIGGERED")
                    llm_click_response = llm_service.generate_click_response(
                        click_context
                    )

                    print("LLM CLICK RESPONSE:", repr(llm_click_response))

                if has_llm_text(llm_click_response):
                    response = llm_click_response.strip()
                else:

                    available_responses = [
                        r for r in click_responses
                        if r != memory["last_response"]
                    ]

                    if available_responses:
                        response = random.choice(available_responses)
                    else:
                        response = random.choice(click_responses)

    memory["last_response"] = response
    save_memory(memory)

    return jsonify({
        "response": response
    })

@app.route("/note", methods=["POST"])
def note():

    data = request.json or {}

    note_text = data.get("note")
    category = data.get("category")

    if not note_text:
        return {
            "status": "error",
            "message": "No note provided"
        }, 400

    add_note(note_text, category=category)

    return {
        "status": "saved",
        "message": random.choice(NOTE_CONFIRMATIONS)
    }

@app.route("/notes/latest", methods=["GET"])
def latest_note():

    note = get_latest_note()

    if not note:
        return jsonify({
            "status": "empty"
        })

    return jsonify(note)

@app.route("/notes", methods=["GET"])
def get_notes():
    return jsonify(load_notes())


@app.route("/notes/<int:note_index>", methods=["DELETE"])
def delete_note_endpoint(note_index):
    deleted_note = delete_note(note_index)

    if deleted_note is None:
        return jsonify({
            "status": "error",
            "message": "Note not found"
        }), 404

    return jsonify({
        "status": "deleted",
        "note": deleted_note
    })


@app.route("/notes/<int:note_index>", methods=["PUT"])
def update_note_endpoint(note_index):
    data = request.json or {}
    note_text = data.get("note")
    category = data.get("category")

    updated_note, error = update_note(note_index, note_text, category)

    if error == "empty":
        return jsonify({
            "status": "error",
            "message": "No note provided"
        }), 400

    if error == "not_found":
        return jsonify({
            "status": "error",
            "message": "Note not found"
        }), 404

    return jsonify({
        "status": "updated",
        "note": updated_note
    })


@app.route("/notes/search", methods=["GET"])
def search_notes_endpoint():
    query = request.args.get("q", "")

    if not isinstance(query, str) or not query.strip():
        return jsonify([])

    matches = search_notes(query.strip())
    return jsonify(matches)

@app.route("/notes/recent", methods=["GET"])
def recent_notes_endpoint():
    return jsonify(get_recent_notes(5))

@app.route("/notes/category/<category>", methods=["GET"])
def notes_by_category_endpoint(category):
    if not isinstance(category, str) or not category.strip():
        return jsonify([])

    matches = filter_notes_by_category(category.strip())
    return jsonify(matches)

@app.route("/notes/suggest-category", methods=["GET"])
def suggest_category_endpoint():
    query = request.args.get("q", "")

    if not isinstance(query, str) or not query.strip():
        return jsonify({"suggestion": None})

    suggestion = suggest_category(query.strip())
    return jsonify({"suggestion": suggestion})

@app.route("/notes/transcribe", methods=["POST"])
def transcribe_note_endpoint():
    uploaded_audio = request.files.get("audio")

    if uploaded_audio is None:
        return jsonify({
            "status": "error",
            "message": "No audio file provided"
        }), 400

    model = get_stt_model()

    if model is None:
        return jsonify({
            "status": "error",
            "message": "Faster-Whisper is not available"
        }), 503

    temp_audio_path = None

    try:
        temp_audio = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        )
        temp_audio_path = temp_audio.name
        temp_audio.close()

        uploaded_audio.save(temp_audio_path)

        segments, _ = model.transcribe(
            temp_audio_path,
            beam_size=STT_BEAM_SIZE,
            language=STT_LANGUAGE
        )

        text = " ".join(
            segment.text.strip()
            for segment in segments
            if segment.text and segment.text.strip()
        ).strip()

        return jsonify({
            "status": "ok",
            "text": text
        })

    except Exception as e:
        print(f"Transcription error: {e}")
        return jsonify({
            "status": "error",
            "message": "Transcription failed"
        }), 500

    finally:
        if temp_audio_path:
            try:
                Path(temp_audio_path).unlink()
            except OSError:
                pass


@app.route("/model_profiles", methods=["GET"])
def model_profiles_endpoint():
    return jsonify({
        "active_profile": get_active_profile_name(),
        "profiles": list_model_profiles(),
    })


@app.route("/model_profiles/active", methods=["POST"])
def set_active_model_profile_endpoint():
    data = request.json or {}
    profile_key = data.get("profile_key")

    if not isinstance(profile_key, str) or not profile_key.strip():
        return jsonify({
            "status": "error",
            "message": "profile_key is required",
        }), 400

    profile_key = profile_key.strip()

    if not set_active_model_profile(profile_key):
        return jsonify({
            "status": "error",
            "message": "Unknown model profile",
        }), 404

    profiles = list_model_profiles()

    return jsonify({
        "status": "success",
        "active_profile": get_active_profile_name(),
        "profile": profiles.get(profile_key, {}),
    })


@app.route("/speak", methods=["POST"])
def speak():
    print("=== ENTERED /SPEAK ===", flush=True)

    data = request.json

    text = data.get(
        "text",
        "Hello Pup."
    )

    print(f"Generating: {text}", flush=True)
    tts_text = sanitize_tts_text(text)

    try:
        pipeline = tts_component.get()
    except Exception as e:
        print(f"TTS initialization error: {e}")
        return jsonify({
            "status": "error",
            "message": "TTS is unavailable"
        }), 503

    generator = pipeline(
        tts_text,
        voice=TTS_VOICE
    )

    audio_file = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False
    )
    audio_file.close()

    chunk_count = 0
    audio_segments = []

    for _, _, audio in generator:
        chunk_count += 1
        audio_segment = audio_segment_to_array(audio)

        if audio_segment is None:
            print(f"TTS chunk {chunk_count}: no audio samples")
            continue

        audio_segments.append(audio_segment)
        print(
            f"TTS chunk {chunk_count}: "
            f"{len(audio_segment)} samples "
            f"({len(audio_segment) / TTS_SAMPLE_RATE:.2f} seconds)"
        )

    print(f"TTS generator finished after {chunk_count} chunk(s)")

    if not audio_segments:
        return jsonify({
            "status": "error",
            "message": "TTS generated no audio"
        }), 500

    if len(audio_segments) == 1:
        combined_audio = audio_segments[0]
    else:
        combined_audio = np.concatenate(audio_segments)

    sf.write(
        audio_file.name,
        combined_audio,
        TTS_SAMPLE_RATE
    )

    return send_file(
        audio_file.name,
        mimetype="audio/wav"
    )

@app.route("/reload_personality", methods=["POST"])
def reload_personality():
    global PERSONALITY

    PERSONALITY = load_personality()

    return jsonify({
        "status": "success"
    })

if __name__ == "__main__":
    app.run(
        host=SPEECH_SERVER_HOST,
        port=SPEECH_SERVER_PORT,
    )
