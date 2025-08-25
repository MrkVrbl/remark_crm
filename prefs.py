import os
import json

GRID_PREFS_FILE = "grid_prefs.json"
CATEGORY_PREFS_FILE = "category_prefs.json"

def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def _save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_grid_prefs():
    return _load_json(GRID_PREFS_FILE, {})

def save_grid_prefs(state):
    _save_json(GRID_PREFS_FILE, state)

def load_category_prefs():
    return _load_json(CATEGORY_PREFS_FILE, {})

def save_category_prefs(data):
    _save_json(CATEGORY_PREFS_FILE, data)
