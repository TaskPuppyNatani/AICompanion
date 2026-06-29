# Rivet AI Companion

A fully local desktop AI companion powered by **llama.cpp**.

Rivet combines natural conversation, speech, image understanding, notes, and desktop notifications into a companion that runs entirely on your own machine. The project is designed around a provider-based architecture, reusable model profiles, and a modern desktop interface while keeping inference local.

---

# Features

## AI & Language
- Local inference using **llama.cpp**
- Provider-neutral LLM architecture
- Profile-based model management
- Fast Chat profile
- Fast Coder profile
- Deep Think profile
- Vision profile
- Runtime profile switching

## Vision
- Image understanding
- Prompt Mode image attachments
- Browse image
- Paste image from clipboard
- Drag & drop image support
- PNG, JPEG, and WebP support

## Prompt Workspace
- Modern reusable Prompt Window
- Multi-line prompt editor
- Ctrl+Enter to submit
- Temporary workspace transcript
- Clear Workspace button
- Workspace geometry persistence
- Active profile shown in window title

## Speech
- Kokoro text-to-speech
- Spoken AI responses
- Speech server architecture

## Notes
- Local notes system
- Voice note support
- Note-aware AI Click responses

## Desktop Integration
- Desktop companion avatar
- AI Click interactions
- Windows notifications
- Notification listener
- Startup greetings

## Personalization
- Preferred user name
- Personalized canned responses
- First-run setup wizard

## Architecture
- Provider abstraction
- ProfileManager
- ProviderLifecycle
- LLMService
- InteractionManager
- Modular desktop application design

---

# Project Structure

```
AICompanion/
├── companion.py
├── companion_app/
├── speech_data/
│   ├── providers/
│   ├── profiles/
│   ├── personality.md
│   ├── notes_data.py
│   └── llm_service.py
├── runtime/
├── assets/
└── docs/
```

---

# Architecture

```
Companion
      │
      ▼
InteractionManager
      │
      ▼
LLMService
      │
      ▼
ProviderFactory
      │
      ▼
LlamaCppProvider
      │
      ▼
llama.cpp
```

---

# Requirements

- Windows
- Python 3.12+
- llama.cpp server
- Compatible GGUF models
- Kokoro TTS
- Faster-Whisper (for voice features)

---

# Getting Started

1. Clone the repository.
2. Create a Python virtual environment.
3. Install the project requirements.
4. Configure your llama.cpp server and model profiles.
5. Launch Rivet.

---

# Current Status

## Completed

- Local llama.cpp backend
- Provider-neutral architecture
- Vision support
- Prompt Workspace
- Working-memory transcript
- User personalization
- Image attachments
- Legacy Ollama removal
- Request logging sanitization

## Planned

- Voice dictation
- Personality template placeholders
- Richer conversation context
- Media Manager integration
- Additional attachment types (PDFs, audio, screenshots)
- Plugin/extension system

---

# Design Goals

- Fully local AI
- Fast desktop interactions
- Modular architecture
- Privacy-first
- Easy to extend
- Portable profile system

---

# License

This project is licensed under the MIT License. See the LICENSE file for details.

---

# Acknowledgements

Powered by the open-source AI ecosystem, including:

- llama.cpp
- Kokoro
- Faster-Whisper
- Flask
- PyQt
