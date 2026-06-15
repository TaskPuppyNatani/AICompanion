from flask import Flask, request, send_file, jsonify
from kokoro import KPipeline
import soundfile as sf
import tempfile
import random
import json
from pathlib import Path

app = Flask(__name__)

MEMORY_FILE = Path("memory.json")

PERSONALITY_FILE = Path("personality.txt")


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

    if event == "startup":

        response = random.choice(startup_responses)

    elif event == "discord":

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