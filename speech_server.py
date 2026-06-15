from flask import Flask, request, send_file, jsonify
from kokoro import KPipeline
import soundfile as sf
import tempfile
import random
import json
import threading
from pathlib import Path
from datetime import datetime

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

app = Flask(__name__)

MEMORY_FILE = Path("memory.json")

PERSONALITY_FILE = Path("personality.txt")

NOTES_FILE = Path(__file__).parent / "notes.json"

NOTE_CONFIRMATIONS = [
    "Saved and logged.",
    "Note captured successfully.",
    "Got it. Your note is saved.",
    "Done. I wrote that down.",
    "Locked in. Note saved.",
    "All set. Note added.",
    "Lombaxed, and loaded!"
]

CATEGORY_KEYWORDS = {
    "Homelab": [
        "docker",
        "container",
        "containers",
        "kubernetes",
        "k8s",
        "proxmox",
        "vm",
        "server",
        "nas",
        "homelab"
    ],
    "Work": [
        "meeting",
        "ticket",
        "jira",
        "sprint",
        "deploy",
        "deadline",
        "client",
        "project"
    ],
    "Personal": [
        "grocery",
        "gym",
        "family",
        "appointment",
        "doctor",
        "errand",
        "home",
        "birthday"
    ]
}

STT_MODEL_NAME = "small.en"
stt_model = None
stt_model_lock = threading.Lock()

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
                    device="cpu",
                    compute_type="int8"
                )

    return stt_model

def load_personality():
    if PERSONALITY_FILE.exists():
        with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
            return f.read()

    return ""

PERSONALITY = load_personality()

def load_memory():
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
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)


print("Loading Kokoro...")

pipeline = KPipeline(lang_code="a")

print("Kokoro ready.")

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

    # Track usage
    if event == "click":
        memory["click_count"] += 1

    elif event == "startup":
        memory["startup_count"] += 1

    save_memory(memory)

    click_responses = [
        "Looks like you're working on me again.",
        "Ratchet seems proud of today's upgrades.",
        "You've clicked me three times already.",
        "I approve of this level of attention."
    ]

    startup_responses = [
        "Good morning, Pup.",
        "Systems online and ready.",
        "Ratchet and I are standing by.",
        "Ready for another day of tinkering?"
    ]

    discord_responses = [
        "Someone sent you a message.",
        "Looks like someone is trying to get your attention.",
        "You've got a Discord notification waiting."
    ]

    discord_sender_responses = [
        f"{sender} sent you a Discord message.",
        f"Looks like {sender} is trying to get your attention.",
        f"You've got a Discord notification from {sender} waiting."
    ]

    if event == "startup":

        response = random.choice(startup_responses)

    elif event == "discord":

        if sender:
            response = random.choice(discord_sender_responses)
        else:
            response = random.choice(discord_responses)

    else:

        if memory["click_count"] == 1:
            response = "Nice to see you today, Pup."

        elif memory["click_count"] == 10:
            response = "You've been checking on me a lot today."

        elif memory["click_count"] == 25:
            response = "I appreciate all the attention."

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
            beam_size=1,
            language="en"
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

@app.route("/speak", methods=["POST"])
def speak():

    data = request.json

    text = data.get(
        "text",
        "Hello Pup."
    )

    print(f"Generating: {text}")

    generator = pipeline(
        text,
        voice="af_heart"
    )

    audio_file = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False
    )

    for _, _, audio in generator:
        sf.write(
            audio_file.name,
            audio,
            24000
        )

    return send_file(
        audio_file.name,
        mimetype="audio/wav"
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001
    )
