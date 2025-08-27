import os
import shutil
import zipfile
import rarfile
import py7zr
import sys
import json
import subprocess

# ==============================================================================
# MUGEN/IKEMEN GO Character Manager v2.1 - Bug Fix Edition
# Reads from config.json, can add, delete, replace, and list characters.
# ==============================================================================

def get_base_path():
    """Gets the base path for the executable or script."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def load_or_create_config(config_path):
    """Loads the config file or creates a default one if it doesn't exist."""
    default_config = {
        "ENGINE_TYPE": "IKEMEN", 
        "GAME_PATH": "C:/path/to/your/ikemen_go",
        "DOWNLOADS_PATH": "C:/path/to/your/downloads/mugen_chars",
        "CLEANUP_ARCHIVES_AFTER_ADD": True
    }
    if not os.path.exists(config_path):
        print("-> config.json not found. Creating a default one now.")
        print(f"   Please edit '{config_path}' with your actual folder paths and re-run the script.")
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=4)
        return None
    try:
        with open(config_path, 'r') as f:
            print("-> Found config.json. Loading settings.")
            config_data = json.load(f)
            # --- BUG FIX: Ensure all keys exist ---
            is_valid = all(key in config_data for key in default_config.keys())
            if not is_valid:
                raise KeyError("One or more keys are missing from config.json")
            return config_data
    except (json.JSONDecodeError, KeyError) as e:
        print(f"ERROR: '{config_path}' is corrupted or missing key values. {e}")
        print("       Please fix it or delete it to regenerate a default file.")
        return None

# --- Character Roster Management ---

def get_roster_path(game_path, engine_type):
    if not game_path: return None # Safety check
    if engine_type.upper() == "IKEMEN":
        return os.path.join(game_path, 'save', 'config.json')
    elif engine_type.upper() == "MUGEN":
        return os.path.join(game_path, 'data', 'select.def')
    return None

def read_roster(roster_path, engine_type):
    chars = []
    if not os.path.exists(roster_path): return []
    try:
        if engine_type.upper() == "IKEMEN":
            with open(roster_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            for entry in config_data.get("Characters", []):
                char_path = entry.get("char", "").replace('\\', '/')
                if char_path.startswith("chars/"):
                    parts = char_path.split('/')
                    if len(parts) > 1:
                        chars.append(parts[1])
        elif engine_type.upper() == "MUGEN":
            with open(roster_path, 'r', encoding='utf-8', errors='ignore') as f:
                in_chars_section = False
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(';'): continue
                    if line.lower() == '[characters]': in_chars_section = True; continue
                    if line.startswith('['): in_chars_section = False
                    if in_chars_section:
                        char_name = line.split(',')[0].split('\\')[0].strip()
                        if char_name: chars.append(char_name)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not read roster file. Reason: {e}")
    return sorted(list(set(chars)))

def write_roster_ikemen(roster_path, chars_to_keep, full_char_list):
    with open(roster_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    # Filter the original full list to preserve special .def paths
    new_char_list = []
    for entry in full_char_list:
        char_path = entry.get("char", "").replace('\\', '/')
        folder_name = char_path.split('/')[1] if char_path.startswith("chars/") and len(char_path.split('/')) > 1 else None
        if folder_name in chars_to_keep:
            new_char_list.append(entry)

    config_data["Characters"] = new_char_list
    with open(roster_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4)

def add_to_roster_ikemen(roster_path, char_folder_name, def_file_name):
    with open(roster_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    new_entry = {"char": f"chars/{char_folder_name}/{def_file_name}"}
    if "Characters" not in config_data or not isinstance(config_data["Characters"], list):
        config_data["Characters"] = []
    config_data["Characters"].append(new_entry)
    with open(roster_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4)

# --- Core Actions ---

def list_characters(roster, chars_folder):
    print("\n--- Currently Installed Characters ---")
    if not roster:
        print("No characters found in roster file.")
        return
    for i, char in enumerate(roster, 1):
        status = "[OK]" if os.path.isdir(os.path.join(chars_folder, char)) else "[FOLDER MISSING]"
        print(f"{i: >3}. {char.ljust(30)} {status}")

def delete_character(roster, roster_path, engine_type, chars_folder):
    list_characters(roster, chars_folder)
    if not roster: return

    try:
        choice_str = input("\nEnter the number of the character to delete (or 0 to cancel): ")
        choice = int(choice_str)
        if choice == 0 or not 0 < choice <= len(roster):
            print("Invalid number. Deletion cancelled.")
            return
    except ValueError:
        print("Invalid input. Deletion cancelled.")
        return

    char_to_delete = roster[choice - 1]
    confirm = input(f"Are you sure you want to PERMANENTLY DELETE '{char_to_delete}'? (y/n): ").lower()
    if confirm != 'y':
        print("Deletion cancelled."); return

    print(f"-> Removing '{char_to_delete}' from the roster...")
    roster.remove(char_to_delete)
    if engine_type.upper() == "IKEMEN":
        with open(roster_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        full_char_list = config_data.get("Characters", [])
        write_roster_ikemen(roster_path, roster, full_char_list)
    
    char_folder_path = os.path.join(chars_folder, char_to_delete)
    if os.path.isdir(char_folder_path):
        print(f"-> Deleting folder: {char_folder_path}")
        shutil.rmtree(char_folder_path)
    
    print(f"'{char_to_delete}' has been successfully deleted.")

def add_characters(roster, roster_path, engine_type, chars_folder, downloads_path, cleanup):
    archives = [f for f in os.listdir(downloads_path) if f.endswith(('.zip', '.rar', '.7z'))]
    if not archives:
        print("\nNo new character archives found in the downloads folder."); return

    print(f"\nFound {len(archives)} new character(s) to install.")
    for archive_name in archives:
        print(f"\n--- Installing: {archive_name} ---")
        archive_path = os.path.join(downloads_path, archive_name)
        temp_extract = os.path.join(get_base_path(), '_temp_extract')
        if os.path.exists(temp_extract): shutil.rmtree(temp_extract)
        os.makedirs(temp_extract)

        if not extract_archive(archive_path, temp_extract): continue
        char_folder_name = find_character_folder(temp_extract)
        if not char_folder_name:
            print("   ERROR: Could not identify a valid character folder. Skipping."); continue
        
        if char_folder_name.lower() in [r.lower() for r in roster]:
            print(f"   WARNING: '{char_folder_name}' is already installed. Skipping."); continue

        source_path = os.path.join(temp_extract, char_folder_name)
        destination_path = os.path.join(chars_folder, char_folder_name)
        shutil.move(source_path, chars_folder)
