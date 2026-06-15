import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)


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

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)
        f.write("\n")
