import json
from pathlib import Path
from config import CONFIG_DIR

CONFIG_PATH = CONFIG_DIR / "config.json"
LEGACY_CONFIG_PATH = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "avatar": "lombax.png",
    "avatar_size": 150,
    "notification_duration": 5000,
    "voice_enabled": True,
    "avatar_position": None,
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


def _write_config():
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)
        f.write("\n")


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
