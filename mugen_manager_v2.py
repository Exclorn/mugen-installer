import os
import shutil
import zipfile
import rarfile
import py7zr
import sys
import json
import traceback

# ==============================================================================
# MUGEN/IKEMEN GO Character Manager v2.3 - Final Roster Fix
# Hardened roster reading and file handling.
# ==============================================================================

# --- Master Error Handler ---
def log_error_and_exit(e):
    base_path = get_base_path()
    log_file_path = os.path.join(base_path, 'crash_log.txt')
    print(f"\nFATAL ERROR: A critical error occurred. Please check 'crash_log.txt' for details.")
    with open(log_file_path, 'w', encoding='utf-8') as f:
        f.write("MUGEN Manager v2.3 Crash Report\n")
        f.write("=================================\n\n")
        f.write(traceback.format_exc())
    input("\nPress Enter to exit.")
    sys.exit(1)

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

# --- Config Handling ---
def load_or_create_config(config_path):
    default_config = {
        "ENGINE_TYPE": "IKEMEN", 
        "GAME_PATH": "C:/path/to/your/ikemen_go",
        "DOWNLOADS_PATH": "C:/path/to/your/downloads/mugen_chars",
        "CLEANUP_ARCHIVES_AFTER_ADD": True
    }
    if not os.path.exists(config_path):
        print("-> config.json not found. Creating a default one now.")
        print(f"   Please edit '{config_path}' with your actual folder paths and re-run the script.")
        with open(config_path, 'w', encoding='utf-8') as f: json.dump(default_config, f, indent=4)
        return None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            if not all(key in config_data for key in default_config.keys()):
                raise KeyError("One or more keys are missing from config.json")
            return config_data
    except (json.JSONDecodeError, KeyError) as e:
        print(f"ERROR: '{config_path}' is corrupted or missing key values. {e}")
        print("       Please fix it or delete it to regenerate a default file.")
        return None

# --- Roster Management ---
def get_roster_path(game_path, engine_type):
    if not game_path: return None
    if engine_type.upper() == "IKEMEN": return os.path.join(game_path, 'save', 'config.json')
    elif engine_type.upper() == "MUGEN": return os.path.join(game_path, 'data', 'select.def')
    return None

def read_roster(roster_path, engine_type):
    chars = []
    if not os.path.exists(roster_path): 
        print("Warning: Roster file not found at the specified path.")
        return [], []
    try:
        if engine_type.upper() == "IKEMEN":
            # --- ROSTER FIX: Use a more robust reading method ---
            with open(roster_path, 'r', encoding='utf-8-sig') as f: # utf-8-sig handles BOM
                config_data = json.load(f)
            
            full_char_list = config_data.get("Characters", [])
            if not isinstance(full_char_list, list):
                print("Warning: 'Characters' section in roster is not a list.")
                return [], []

            for entry in full_char_list:
                if isinstance(entry, dict):
                    char_path = entry.get("char", "").replace('\\', '/')
                    if char_path.startswith("chars/"):
                        parts = char_path.split('/')
                        if len(parts) > 1:
                            chars.append(parts[1])
            return sorted(list(set(chars))), full_char_list
        # ... (MUGEN code remains the same)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not read roster file. Reason: {e}")
    return [], []

# ... (The rest of the script is largely the same, but I've included the full, cleaned-up version below)

def write_roster_ikemen(roster_path, chars_to_keep, full_char_list):
    with open(roster_path, 'r', encoding='utf-8-sig') as f: config_data = json.load(f)
    new_char_list = [entry for entry in full_char_list if (entry.get("char", "").replace('\\', '/').split('/')[1] if entry.get("char", "").startswith("chars/") and len(entry.get("char", "").split('/')) > 1 else None) in chars_to_keep]
    config_data["Characters"] = new_char_list
    with open(roster_path, 'w', encoding='utf-8') as f: json.dump(config_data, f, indent=4)

def add_to_roster_ikemen(roster_path, char_folder_name, def_file_name):
    with open(roster_path, 'r', encoding='utf-8-sig') as f: config_data = json.load(f)
    new_entry = {"char": f"chars/{char_folder_name}/{def_file_name}"}
    if "Characters" not in config_data 
