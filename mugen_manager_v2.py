import os
import shutil
import zipfile
import rarfile
import py7zr
import sys
import json
import traceback

# ==============================================================================
# MUGEN/IKEMEN GO Character Manager v2.7 - Diagnostic Edition
# Added a diagnostic tool to inspect the roster file directly.
# ==============================================================================

def log_error_and_exit(e):
    base_path = get_base_path()
    log_file_path = os.path.join(base_path, 'crash_log.txt')
    print(f"\nFATAL ERROR: A critical error occurred. Please check 'crash_log.txt' for details.")
    with open(log_file_path, 'w', encoding='utf-8') as f:
        f.write("MUGEN Manager v2.7 Crash Report\n=================================\n\n")
        f.write(traceback.format_exc())
    input("\nPress Enter to exit.")
    sys.exit(1)

def get_base_path():
    if getattr(sys, 'frozen', False): return os.path.dirname(sys.executable)
    else: return os.path.dirname(os.path.abspath(__file__))

# ... (All other functions from v2.6 remain the same. Full code provided below for simplicity) ...
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
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            config_data = json.load(f)
        if not all(key in config_data for key in default_config.keys()):
            raise KeyError("One or more keys are missing from config.json")
        return config_data
    except (json.JSONDecodeError, KeyError) as e:
        print(f"ERROR: Could not load '{config_path}'. It may be corrupted. {e}")
        return None

def get_roster_path(game_path, engine_type):
    if not game_path: return None
    if engine_type.upper() == "IKEMEN": return os.path.join(game_path, 'save', 'config.json')
    return None

def read_roster(roster_path):
    simple_roster, full_roster_data = [], []
    if not os.path.exists(roster_path): 
        print("Warning: Roster file not found.")
        return [], []
    try:
        with open(roster_path, 'r', encoding='utf-8-sig') as f:
            config_data = json.load(f)
        full_roster_data = config_data.get("Characters", [])
        if not isinstance(full_roster_data, list):
            print("Warning: 'Characters' section in roster is malformed.")
            return [], []
        for entry in full_roster_data:
            if isinstance(entry, dict) and "char" in entry:
                char_path = entry["char"].replace('\\', '/')
                path_parts = char_path.split('/')
                if len(path_parts) > 1 and path_parts[0].lower() == 'chars':
                    simple_roster.append(path_parts[1])
        return sorted(list(set(simple_roster))), full_roster_data
    except Exception as e:
        print(f"ERROR: Failed to read and parse roster file. Reason: {e}")
    return [], []

def write_roster_ikemen(roster_path, new_full_roster_data):
    try:
        with open(roster_path, 'r', encoding='utf-8-sig') as f:
            config_data = json.load(f)
        config_data["Characters"] = new_full_roster_data
        with open(roster_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
        return True
    except Exception as e:
        print(f"ERROR: Could not write to roster file. Reason: {e}")
        return False

def list_characters(roster, chars_folder):
    print("\n--- Currently Installed Characters ---")
    if not roster:
        print("No characters found in roster file."); return
    for i, char in enumerate(roster, 1):
        status = "[OK]" if os.path.isdir(os.path.join(chars_folder, char)) else "[FOLDER MISSING]"
        print(f"{i: >3}. {char.ljust(30)} {status}")

def delete_character(roster, roster_path, full_roster_data, chars_folder):
    list_characters(roster, chars_folder)
    if not roster: return
    try:
        choice = int(input("\nEnter number of character to delete (0 to cancel): "))
        if not 0 < choice <= len(roster):
            print("Invalid number. Deletion cancelled."); return
    except ValueError:
        print("Invalid input. Deletion cancelled."); return

    char_to_delete = roster[choice - 1]
    if input(f"PERMANENTLY DELETE '{char_to_delete}'? (y/n): ").lower() != 'y':
        print("Deletion cancelled."); return

    print(f"-> Removing '{char_to_delete}' from the roster...")
    new_full_roster_data = [entry for entry in full_roster_data if not (entry.get("char", "").replace('\\','/').startswith(f'chars/{char_to_delete}/'))]
    
    if write_roster_ikemen(roster_path, new_full_roster_data):
        char_folder_path = os.path.join(chars_folder, char_to_delete)
        if os.path.isdir(char_folder_path):
            print(f"-> Deleting folder: {char_folder_path}")
            shutil.rmtree(char_folder_path)
        print(f"'{char_to_delete}' successfully deleted.")

def add_characters(roster_path, chars_folder, downloads_path, cleanup):
    archives = [f for f in os.listdir(downloads_path) if f.endswith(('.zip', '.rar', '.7z'))]
    if not archives:
        print("\nNo new character archives found."); return
    
    simple_roster, full_roster_data = read_roster(roster_path)
    
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
        
        if char_folder_name.lower() in [r.lower() for r in simple_roster]:
            print(f"   WARNING: '{char_folder_name}' is already installed. Skipping."); continue

        source_path = os.path.join(temp_extract, char_folder_name)
        destination_path = os.path.join(chars_folder, char_folder_name)
        if os.path.exists(destination_path):
             print(f"   WARNING: Folder '{char_folder_name}' already exists. Skipping."); continue
        shutil.move(source_path, chars_folder)

        def_file = find_def_file(destination_path)
        if not def_file:
            print(f"   WARNING: No .def file found for '{char_folder_name}'. Not added to roster."); continue
        
        new_entry = {"char": f"chars/{char_folder_name}/{def_file}"}
        full_roster_data.append(new_entry)
        
        if write_roster_ikemen(roster_path, full_roster_data):
            print(f"   '{char_folder_name}' successfully installed and added to roster.")
        
        if cleanup: os.remove(archive_path)
        shutil.rmtree(temp_extract)

def run_diagnostics(roster_path):
    print("\n--- Running Roster Diagnostics ---")
    output_file = os.path.join(get_base_path(), "roster_diagnostics.txt")
    try:
        if not os.path.exists(roster_path):
            message = f"Error: Roster file does not exist at path:\n{roster_path}"
            print(message)
            with open(output_file, 'w', encoding='utf-8') as f: f.write(message)
            return

        with open(roster_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        
        print(f"-> Successfully read the roster file.")
        
        data = json.loads(content)
        print("-> Successfully parsed file as JSON.")

        if "Characters" in data:
            print("-> Found the 'Characters' key.")
            char_data = data["Characters"]
            message = "--- Start of 'Characters' section ---\n\n"
            message += json.dumps(char_data, indent=4)
            message += "\n\n--- End of 'Characters' section ---"
            with open(output_file, 'w', encoding='utf-8') as f: f.write(message)
            print(f"Success! The content of the 'Characters' section has been saved to:\n{output_file}")
        else:
            message = "Error: The JSON file is valid, but it does not contain a 'Characters' key."
            print(message)
            with open(output_file, 'w', encoding='utf-8') as f: f.write(message)

    except Exception as e:
        message = f"A critical error occurred during diagnostics:\n\n{traceback.format_exc()}"
        print(message)
        with open(output_file, 'w', encoding='utf-8') as f: f.write(message)

def find_def_file(char_folder_path):
    char_folder_name = os.path.basename(char_folder_path)
    if os.path.isfile(os.path.join(char_folder_path, f"{char_folder_name}.def")): return f"{char_folder_name}.def"
    for file in os.listdir(char_folder_path):
        if file.lower().endswith('.def'): return file
    return None

def extract_archive(archive_path, extract_to):
    try:
        if archive_path.endswith('.zip'): with zipfile.ZipFile(archive_path, 'r') as z: z.extractall(extract_to)
        elif archive_path.endswith('.rar'): with rarfile.RarFile(archive_path, 'r') as r: r.extractall(extract_to)
        elif archive_path.endswith('.7z'): with py7zr.SevenZipFile(archive_path, 'r') as s: s.extractall(extract_to)
        return True
    except Exception as e:
        print(f"   ERROR extracting {os.path.basename(archive_path)}: {e}"); return False

def find_character_folder(base_path):
    contents = os.listdir(base_path)
    if not contents: return None
    if len(contents) == 1 and os.path.isdir(os.path.join(base_path, contents[0])): return contents[0]
    for item in contents:
        item_path = os.path.join(base_path, item)
        if os.path.isdir(item_path) and find_def_file(item_path): return item
    potential_folders = [d for d in contents if os.path.isdir(os.path.join(base_path, d))]
    if potential_folders: return potential_folders[0]
    return None

def main_loop():
    base_path = get_base_path()
    config_path = os.path.join(base_path, 'config.json')
    config = load_or_create_config(config_path)

    if config is None:
        input("\nPress Enter to exit."); return
    
    GAME_PATH = config.get("GAME_PATH")
    ENGINE_TYPE = config.get("ENGINE_TYPE", "IKEMEN")
    DOWNLOADS_PATH = config.get("DOWNLOADS_PATH")
    
    roster_path = get_roster_path(GAME_PATH, ENGINE_TYPE)
    if not roster_path:
        print(f"\nERROR: Roster path could not be determined for '{ENGINE_TYPE}' at '{GAME_PATH}'.");
        input("Press Enter to exit."); return

    CHARS_FOLDER = os.path.join(GAME_PATH, 'chars')

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n MUGEN/IKEMEN GO Character Manager ".center(50, "="))
        print("1. List all installed characters")
        print("2. Add new character(s) from downloads folder")
        print("3. Delete a character")
        print("4. Exit")
        print("5. Run Roster Diagnostics")
        choice = input("Please choose an option (1-5): ")
        
        if choice == '5':
            run_diagnostics(roster_path)
        else:
            simple_roster, full_roster_data = read_roster(roster_path)
            if choice == '1': list_characters(simple_roster, CHARS_FOLDER)
            elif choice == '2': add_characters(roster_path, CHARS_FOLDER, DOWNLOADS_PATH, config.get("CLEANUP_ARCHIVES_AFTER_ADD", True))
            elif choice == '3': delete_character(simple_roster, roster_path, full_roster_data, CHARS_FOLDER)
            elif choice == '4': print("Exiting."); break
            else: print("Invalid option, please try again.")
        
        input("\nPress Enter to return to the menu...")

if __name__ == "__main__":
    try:
        main_loop()
    except Exception as e:
        log_error_and_exit(e)
