# Rivet Runtime Dependencies

This file tracks the runtime dependencies required for Rivet to function, with emphasis on the current Windows development setup and portable llama.cpp runtime.

---

# 1. Core Runtime Environment

## Python

* Python 3.12.x
* Rivet is currently run from a local `.venv`

## Current LLM Backend

Rivet is a llama.cpp-only application at runtime.

* `llama-server`
* Disk-backed model profiles in `speech_data/profiles/`
* Provider lifecycle management owned by the speech server

## Current Runtime Entry Points

* `companion.py`
* `speech_server.py`

---

# 2. Required Python Runtime Packages

These packages are required for Rivet's currently working feature set.

## UI / app runtime

* `PyQt6`
* `requests`
* `Flask`

## LLM / AI runtime

* local `llama-server`
* `faster-whisper==1.2.1`
* `kokoro==0.9.4`
* `numpy`

## Voice note / audio runtime

* `sounddevice`
* `soundfile`
* `numpy`

---

# 3. Feature-to-Dependency Mapping

## Core Rivet app / UI

Used for the desktop companion, local HTTP calls, and app behavior.

* `PyQt6`
* `requests`

## Speech server / local API

Used by Rivet's local speech and chat service flow.

* `Flask`
* `requests`

## LLM generation

LLM generation is routed through the provider abstraction to llama.cpp.

* local `llama-server`
* GGUF model files referenced by disk-backed profiles
* optional `mmproj` files for vision profiles

## TTS

Used for Rivet's speech generation.

* `kokoro==0.9.4`

## Voice transcription / voice notes

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
* llama.cpp provider reachable
* active profile model available

## Prompt Mode and Vision prompts

Requires:

* active llama.cpp profile
* model files referenced by the selected profile
* vision model plus `mmproj` file for image prompts

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

* llama.cpp: local `llama-server`
* faster-whisper: `1.2.1`
* kokoro: `0.9.4`
* model profiles:
  * Fast Chat
  * Fast Coder
  * Deep Think
  * Vision

Additional confirmed runtime package requirement for voice notes:

* `sounddevice`

---

# 6. Current Architecture Notes

Rivet currently uses:

* Rivet UI / companion app
* local speech server
* provider-backed generation through llama.cpp
* model profile system for selecting provider startup inputs
* provider-neutral message architecture
* lazy TTS initialization through the speech server

The provider abstraction remains in place for future extensibility, but llama.cpp is the only supported runtime provider.

---

# 7. Portability Notes

Rivet is being prepared for:

* running from a moved project folder / external drive
* flash-drive portability
* self-contained launcher flow

This dependency file should be updated whenever:

* a new runtime package is required for an existing feature
* the llama.cpp runtime strategy changes
* the default model/profile set changes
* the launcher/runtime packaging strategy changes
* a feature depends on a package that is not installed by default in the base `.venv`

---

# 8. Things to keep updated in this file

When Rivet changes, update this file if any of the following happen:

* llama.cpp version changes
* model profile requirements change
* Kokoro version changes
* faster-whisper version changes
* a new voice/audio dependency is added
* runtime packaging changes for portable/self-contained deployment
