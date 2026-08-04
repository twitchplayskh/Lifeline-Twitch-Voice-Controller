"""Loading and saving of config.json (settings persisted between runs)."""

import json
import logging
import os
import shutil

logger = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

DEFAULT_CONFIG = {
    "channel": "",
    "oauth_token": "",
    "audio_folder": "",
    "output_device": "",
    "virtual_device": "",
    "cooldown": 1.5,
    "volume": 1.0,
    "custom_commands": [],
}


def load_config(path: str = CONFIG_FILE) -> dict:
    """
    Load settings from `path`, falling back to defaults for anything missing.

    If the file is corrupt JSON, it's backed up (as `<path>.corrupted`) rather
    than silently discarded, so the user doesn't lose their settings history
    without a trace.
    """
    config = dict(DEFAULT_CONFIG)
    if not os.path.exists(path):
        return config

    try:
        with open(path, encoding="utf-8") as config_file:
            saved_values = json.load(config_file)
        config.update(saved_values)
    except json.JSONDecodeError:
        backup_path = path + ".corrupted"
        logger.warning("Config file is corrupt JSON; backing up to %s", backup_path)
        shutil.copy(path, backup_path)
    except OSError as error:
        logger.warning("Could not read config file %s: %s", path, error)

    return config


def save_config(config: dict, path: str = CONFIG_FILE) -> None:
    """
    Save `config` to `path` atomically (write to a temp file, then rename)
    so a crash mid-write can't corrupt the existing config.
    """
    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as temp_file:
            json.dump(config, temp_file, indent=2)
        os.replace(temp_path, path)
    except OSError as error:
        logger.error("Failed to save config to %s: %s", path, error)
        raise
