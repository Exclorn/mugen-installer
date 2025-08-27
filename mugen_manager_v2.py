import os
import shutil
import zipfile
import rarfile
import py7zr
import sys
import json
import traceback

# ==============================================================================
# MUGEN/IKEMEN GO Character Manager v4.0 - The select.def Edition
# This version is CORRECTED to work with the classic data/select.def roster file.
# ==============================================================================

def log_error_and_exit(e):
    base_path = get_base_path()
    log_file_path = os.path.join(base_path, 'crash_log.txt')
    print(f"\nFATAL ERROR: A critical error occurred. Please check 'crash_log.txt' for details.")
    with open(log_file_path, 'w', encoding='utf-8') as f:
        f.write("MUGEN Manager v4.0 Crash Report\n=================================\n\n")
        f.write(traceback.format_exc())
    input("\nPress Enter to exit.")
    sys.exit(1)

def get_base_path():
    if getattr(sys, 'frozen', False): return os.path.dirname(sys.executable)
    else: return os.path.dirname(os.path.abspath(__file__))

def load_or_create_config(config_path):
    default_config = {
        "GAME_PATH": "C:/path/to/your/game_folder",
        "DOWNLOADS_PATH": "C:/path/to/your/downloads/folder",
        "CLEANUP_ARCHIVES_AFTER_ADD": True
    }
    if not os.path.exists(config_path):
        print("-> config.json not found. Creating a default one now.")
        print(f"   Please edit '{config_path}' with your correct paths and re-run.")
        with open(config_path, 'w', encoding='utf-8') as f: json.dump(default_config, f, indent=4)
        return None
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f: return json.load(f)
    except Exception as e:
        print(f"ERROR: Could not load '{config_path}'. {e}"); return None

def read_roster_selectdef(roster_path):
    chars = []
    if not os.path.exists(roster_path): return []
    try:
        with open(roster_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            in_chars_section = False
            for line in f:
                line = line.strip()
                if not line or line.startswith(';'): continue
                if line.lower().startswith('[characters]'): in_chars_section = True; continue
                if line.startswith('['): in_chars_section = False
                if in_chars_section:
                    char_name = line.split(',')[0].strip()
                    if char_name and char_name.lower() != 'randomselect':
                        chars.append(char_name)
    except Exception as e:
        print(f"Warning: Could not read select.def. Reason: {e}")
    return sorted(list(set(chars)))

def write_roster_selectdef(roster_path, char_list):
    try:
        with open(roster_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            lines = f.readlines()
        
        with open(roster_path, 'w', encoding='utf-8') as f:
            in_chars_section = False
            wrote_new_chars = False
            for line in lines:
                if line.strip().lower().startswith('[characters]'):
                    f.write(line)
                    for char in sorted(char_list):
                        f.write(f"{char}\n")
                    f.write("randomselect\n")
                    in_chars_section = True
                    wrote_new_chars = True
                elif in_chars_section and (line.strip().startswith('[') or not line.strip()):
                    in_chars_section = False
                    f.write(line)
                elif not in_chars_section:
                    f.write(line)
        if not wrote_new_chars:
             print("ERROR: Could not find [Characters] section to write to in select.def.")
             return False
        return True
    except Exception as e:
        print(f"ERROR: Could not write to select.def. Reason: {e}")
        return False

def list_characters(roster, chars_folder):
    print("\n--- Currently Installed Characters ---")
    if not roster:
        print("No characters found in roster file."); return
    for i, char in enumerate(roster, 1):
        status = "[OK]" if os.path.isdir(os.path.join(chars_folder, char)) or '\\' in char or '/' in char else "[FOLDER MISSING]"
        print(f"{i: >3}. {char.ljust(40)} {status}")

def delete_character(roster, roster_path, chars_folder):
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

    print(f"-> Removing '{char_to_delete}' from select.def...")
    roster.remove(char_to_delete)
    
    if write_roster_selectdef(roster_path, roster):
        # Only delete folder if it's a simple entry
        if '\\' not in char_to_delete and '/' not in char_to_delete:
            char_folder_path = os.path.join(chars_folder, char_to_delete)
            if os.path.isdir(char_folder_path):
                print(f"-> Deleting folder: {char_folder_path}")
                shutil.rmtree(char_folder_path)
        print(f"'{char_to_delete}' successfully deleted.")

def add_characters(roster, roster_path, chars_folder, downloads_path, cleanup):
    archives = [f for f in os.listdir(downloads_path) if f.endswith(('.zip', '.rar', '.7z'))]
    if not archives:
        print("\nNo new character archives found."); return
    
    print(f"\nFound {len(archives)} new character(s) to install.")
    newly_added_chars = []
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
        
        if char_folder_name.lower() in [r.lower().split('\\')[0].split('/')[0] for r in roster]:
            print(f"   WARNING: '{char_folder_name}' is already installed. Skipping."); continue

        source_path = os.path.join(temp_extract, char_folder_name)
        destination_path = os.path.join(chars_folder, char_folder_name)
        if os.path.exists(destination_path):
             print(f"   WARNING: Folder '{char_folder_name}' already exists. Skipping."); continue
        shutil.move(source_path, chars_folder)
        
        roster.append(char_folder_name)
        newly_added_chars.append(char_folder_name)
        print(f"   '{char_folder_name}' successfully installed.")
        
        if cleanup: os.remove(archive_path)
        shutil.rmtree(temp_extract)

    if newly_added_chars:
        print("\nUpdating select.def with new characters...")
        write_roster_selectdef(roster_path, roster)
        print("Roster updated successfully.")

# --- Helper functions (unchanged) ---
def find_def_file(char_folder_path):
    char_folder_name = os.path.basename(char_folder_path)
    if os.path.isfile(os.path.join(char_folder_path, f"{char_folder_name}.def")): return f"{char_folder_name}.def"
    for file in os.listdir(char_folder_path):
        if file.lower().endswith('.def'): return file
    return None

def extract_archive(archive_path, extract_to):
    try:
        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as z: z.extractall(extract_to)
        elif archive_path.endswith('.rar'):
            with rarfile.RarFile(archive_path, 'r') as r: r.extractall(extract_to)
        elif archive_path.endswith('.7z'):
            with py7zr.SevenZipFile(archive_path, 'r') as s: s.extractall(path=extract_to)
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
    DOWNLOADS_PATH = config.get("DOWNLOADS_PATH")
    
    roster_path = os.path.join(GAME_PATH, 'data', 'select.def')
    if not os.path.exists(roster_path):
        print(f"\nERROR: select.def not found in the data folder of:\n{GAME_PATH}");
        input("Press Enter to exit."); return

    CHARS_FOLDER = os.path.join(GAME_PATH, 'chars')

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n MUGEN/IKEMEN GO Character Manager (select.def Edition) ".center(60, "="))
        print("1. List all installed characters")
        print("2. Add new character(s) from downloads folder")
        print("3. Delete a character")
        print("4. Exit")
        choice = input("Please choose an option (1-4): ")
        
        current_roster = read_roster_selectdef(roster_path)

        if choice == '1': list_characters(current_roster, CHARS_FOLDER)
        elif choice == '2': add_characters(current_roster, roster_path, CHARS_FOLDER, DOWNLOADS_PATH, config.get("CLEANUP_ARCHIVES_AFTER_ADD", True))
        elif choice == '3': delete_character(current_roster, roster_path, CHARS_FOLDER)
        elif choice == '4': print("Exiting."); break
        else: print("Invalid option, please try again.")
        
        input("\nPress Enter to return to the menu...")

if __name__ == "__main__":
    try:
        main_loop()
    except Exception as e:
        log_error_and_exit(e)
