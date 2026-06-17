from kokoro import KPipeline
import soundfile as sf
import sys
from config import AUDIO_DIR, TTS_LANG_CODE, TTS_VOICE, TTS_SAMPLE_RATE

if len(sys.argv) < 2:
    print("Usage: python speak.py \"text to speak\"")
    sys.exit(1)

text = " ".join(sys.argv[1:])

print(f"Generating speech for: {text}")

pipeline = KPipeline(lang_code=TTS_LANG_CODE)

generator = pipeline(
    text,
    voice=TTS_VOICE
)

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
output_path = AUDIO_DIR / "output.wav"

for i, (gs, ps, audio) in enumerate(generator):
    sf.write(output_path, audio, TTS_SAMPLE_RATE)

print(f"Saved {output_path}")