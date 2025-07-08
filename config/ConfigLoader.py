# config/ConfigLoader.py
import json
import os
import shutil

CONFIG_FILE = "config.json"
DEFAULT_CONFIG_FILE = "config.default.json" # Make sure you still have this file

def load_config():
    """
    Loads the configuration from config.json.
    If config.json is missing or corrupt, it is restored from the template.
    """
    if not os.path.exists(CONFIG_FILE):
        print(f"INFO: {CONFIG_FILE} not found. Creating from template...")
        try:
            shutil.copyfile(DEFAULT_CONFIG_FILE, CONFIG_FILE)
        except Exception as e:
            print(f"FATAL: Could not create config file: {e}")
            return {}
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        print(f"WARN: Could not read {CONFIG_FILE}, restoring from backup.")
        try:
            shutil.copyfile(DEFAULT_CONFIG_FILE, CONFIG_FILE)
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"FATAL: Could not restore config file: {e}")
            return {}

def save_config(data):
    """Saves the provided data to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"ERROR: Could not save config file: {e}")