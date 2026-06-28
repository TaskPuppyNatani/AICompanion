# Rivet Runtime Dependencies

This file tracks the **runtime dependencies required for Rivet to function**, with emphasis on the current Windows development setup and future portability work.

---

# 1. Core Runtime Environment

## Python

* **Python 3.12.x**
* Rivet is currently being run from a local `.venv`

## Current LLM Backend

* Provider-based LLM backend
* Current active provider in development:

  * `llama_cpp`
  * `models/gemma3.gguf`

* Supported fallback provider:

  * **Ollama 0.30.x**

## Current Runtime Entry Points

* `companion.py`
* `speech_server.py`

---

# 2. Required Python Runtime Packages

These packages are required for Rivet’s currently working feature set.

## UI / app runtime

* `PyQt6`
* `requests`
* `Flask`

## LLM / AI runtime

* `faster-whisper==1.2.1`
* `kokoro==0.9.4`
* `numpy`

## Voice note / audio runtime

* `sounddevice`
* `soundfile`
* `numpy`

---

# 3. Feature-to-Dependency Mapping

## A. Core Rivet app / UI

Used for the desktop companion, local HTTP calls, and app behavior.

* `PyQt6`
* `requests`

## B. Speech server / local API

Used by Rivet’s local speech and chat service flow.

* `Flask`
* `requests`

## C. LLM generation

LLM generation is routed through the provider abstraction.

* **llama.cpp** via local `llama-server`
* **Ollama 0.30.x**
* active provider selected in `speech_data/provider_factory.py`

## D. TTS

Used for Rivet’s speech generation.

* `kokoro==0.9.4`

## E. Voice transcription / voice notes

Used for speech-to-text and microphone voice note handling.

* `faster-whisper==1.2.1`
* `sounddevice`
* `soundfile`
* `numpy`

---

# 4. Current Known Runtime Requirements by Feature

## AI click responses / notification reactions

Requires:

* Rivet Python environment
* Flask speech server path working
* active LLM provider reachable
* active provider model available

## Speech / spoken output

Requires:

* `kokoro`
* Rivet speech server running

## Voice notes

Requires:

* `faster-whisper`
* `sounddevice`
* `soundfile`
* `numpy`

If `sounddevice` is missing, voice note capture will fail with the runtime message:

> Voice Note requires sounddevice, soundfile, and numpy.

---

# 5. Current Tested / Known Working Runtime Stack

This reflects the currently known working stack in the project as of the latest Rivet work:

* **Ollama**: `0.30.x`
* **llama.cpp**: local `llama-server`
* **faster-whisper**: `1.2.1`
* **kokoro**: `0.9.4`
* **default llama.cpp model**: `models/gemma3.gguf`

Additional confirmed runtime package requirement for voice notes:

* **sounddevice**

---

# 6. Current Architecture Notes

## Current state

Rivet currently uses:

* Rivet UI / companion app
* local speech server
* provider-backed text generation
* model profile system for selecting the active model
* lazy TTS initialization through the speech server

## Provider architecture

Rivet now uses an **LLM provider abstraction layer**. The current portable path uses **llama.cpp**, while **Ollama** remains a supported provider.

---

# 7. Portability Notes

## Current portability goal

Rivet is being prepared for:

* running from a moved project folder / external drive
* eventual flash-drive portability
* eventual self-contained launcher flow

## Important implication

This dependency file should be updated whenever:

* a new runtime package is required for an existing feature
* the active LLM backend changes
* the launcher/runtime packaging strategy changes
* a feature depends on a package that is not installed by default in the base `.venv`

---

# 8. Things to keep updated in this file

When Rivet changes, update this file if any of the following happen:

* Ollama version changes
* llama.cpp version changes
* default model changes
* Kokoro version changes
* faster-whisper version changes
* a new voice/audio dependency is added
* the active provider changes
* runtime packaging changes for portable/self-contained deployment
