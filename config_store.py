import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

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
