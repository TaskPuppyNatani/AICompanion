import json
from copy import deepcopy
from pathlib import Path
from config import CONFIG_DIR
from config import OLLAMA_MODEL_NAME

CONFIG_PATH = CONFIG_DIR / "config.json"
LEGACY_CONFIG_PATH = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "avatar": "lombax.png",
    "avatar_size": 150,
    "notification_duration": 5000,
    "voice_enabled": True,
    "avatar_position": None,
    "active_model_profile": "fast",
    "model_profiles": {
        "fast": {
            "display_name": "Fast",
            "model_name": OLLAMA_MODEL_NAME,
        },
        "balanced": {
            "display_name": "Balanced",
            "model_name": "qwen2.5-coder:3b",
        },
        "smart": {
            "display_name": "Smart",
            "model_name": "gemma4:26b",
        },
    },
}

CONFIG_DIR.mkdir(parents=True, exist_ok=True)

if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
elif LEGACY_CONFIG_PATH.exists():
    with open(LEGACY_CONFIG_PATH, "r") as f:
        config = json.load(f)

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)
        f.write("\n")
else:
    config = dict(DEFAULT_CONFIG)

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)
        f.write("\n")

if not isinstance(config.get("voice_enabled", True), bool):
    config["voice_enabled"] = True

if not isinstance(config.get("active_model_profile", "fast"), str):
    config["active_model_profile"] = "fast"

if not isinstance(config.get("model_profiles"), dict):
    config["model_profiles"] = deepcopy(DEFAULT_CONFIG["model_profiles"])


def _write_config():
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)
        f.write("\n")


def get_config_value(key, default=None):
    return config.get(key, default)


def set_config_value(key, value):
    config[key] = value
    _write_config()


def saved_avatar_position():
    position = config.get("avatar_position")

    if not isinstance(position, dict):
        return None

    try:
        return int(position["x"]), int(position["y"])
    except (KeyError, TypeError, ValueError):
        return None


def save_avatar_position(new_x, new_y):
    config["avatar_position"] = {
        "x": int(new_x),
        "y": int(new_y)
    }

    _write_config()


def voice_enabled():
    value = config.get("voice_enabled", True)

    if isinstance(value, bool):
        return value

    return True


def save_voice_enabled(enabled):
    config["voice_enabled"] = bool(enabled)
    _write_config()
