from flask import Flask, request, send_file
from kokoro import KPipeline
import soundfile as sf
import tempfile

app = Flask(__name__)

print("Loading Kokoro...")

pipeline = KPipeline(lang_code="a")

print("Kokoro ready.")


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