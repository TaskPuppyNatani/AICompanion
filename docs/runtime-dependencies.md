# Rivet Runtime Dependencies

This file tracks the **runtime dependencies required for Rivet to function**, with emphasis on the current Windows development setup and future portability work.

---

# 1. Core Runtime Environment

## Python

* **Python 3.12.x**
* Rivet is currently being run from a local `.venv`

## Current LLM Backend

* **Ollama 0.30.x**
* Current default model:

  * `phi4-mini:latest`

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

Current provider path still uses **Ollama** as the active backend.

* **Ollama 0.30.x**
* active configured model profile target (currently defaults to `phi4-mini:latest`)

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
* Ollama reachable
* active model profile resolves to a valid Ollama model

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
* **faster-whisper**: `1.2.1`
* **kokoro**: `0.9.4`
* **default model**: `phi4-mini:latest`

Additional confirmed runtime package requirement for voice notes:

* **sounddevice**

---

# 6. Current Architecture Notes

## Current state

Rivet currently uses:

* Rivet UI / companion app
* local speech server
* Ollama backend for text generation
* model profile system for selecting the active model

## In-progress architecture direction

Rivet is being refactored toward an **LLM provider abstraction layer** so that Ollama can later be replaced with a more self-contained backend, likely based on **llama.cpp**.

That means this dependency list should be treated as the **current Ollama-era runtime dependency list**, not the final long-term portable dependency target.

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
* default model changes
* Kokoro version changes
* faster-whisper version changes
* a new voice/audio dependency is added
* Ollama is replaced by llama.cpp or another backend
* runtime packaging changes for portable/self-contained deployment
