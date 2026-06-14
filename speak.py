from kokoro import KPipeline
import soundfile as sf
import sys

if len(sys.argv) < 2:
    print("Usage: python speak.py \"text to speak\"")
    sys.exit(1)

text = " ".join(sys.argv[1:])

print(f"Generating speech for: {text}")

pipeline = KPipeline(lang_code="a")

generator = pipeline(
    text,
    voice="af_heart"
)

for i, (gs, ps, audio) in enumerate(generator):
    sf.write("output.wav", audio, 24000)

print("Saved output.wav")