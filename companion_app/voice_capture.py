import tempfile
from pathlib import Path

try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf_audio
except Exception:
    np = None
    sd = None
    sf_audio = None


def audio_dependencies_available():
    return np is not None and sd is not None and sf_audio is not None


def build_audio_callback(audio_frames):
    def audio_callback(indata, frames, callback_time, status):
        if status:
            print(f"Recording status: {status}")
        audio_frames.append(indata.copy())

    return audio_callback


def start_input_stream(sample_rate, callback):
    stream = sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        callback=callback
    )
    stream.start()
    return stream


def stop_and_close_stream(stream):
    if stream is None:
        return

    try:
        stream.stop()
        stream.close()
    except Exception as close_error:
        print(f"Voice stream close error: {close_error}")


def create_temp_wav_from_frames(audio_frames, sample_rate):
    waveform = np.concatenate(audio_frames, axis=0)

    temp_audio = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False
    )
    temp_audio_path = temp_audio.name
    temp_audio.close()

    sf_audio.write(temp_audio_path, waveform, sample_rate)
    return temp_audio_path


def cleanup_temp_audio_file(temp_audio_path):
    if not temp_audio_path:
        return

    try:
        Path(temp_audio_path).unlink()
    except OSError:
        pass
