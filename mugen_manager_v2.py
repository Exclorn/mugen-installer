import os
import shutil
import zipfile
import rarfile
import py7zr
import sys
import json
import traceback
from datetime import datetime

# ==============================================================================
# MUGEN/IKEMEN GO Character Manager v5.0 - The QoL Update
# - Works with select.def
# - Adds characters AND stages
# - Automatically backs up select.def before any changes
# - Smarter logic and cleaner UI
# ==============================================================================

def log_error_and_exit(e):
    base_path = get_base_path()
    log_file_path = os.path.join(base_path, 'crash_log.txt')
    print(f"\nFATAL ERROR: A critical error occurred. Please check 'crash_log.txt' for details.")
    with open(log_file_path, 'w', encoding='utf-8') as f:
        f.write("MUGEN Manager v5.0 Crash Report\n=================================\n\n")
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

def backup_roster(roster_path):
    try:
        backup_dir = os.path.join(os.path.dirname(roster_path), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"select.def.{timestamp}.bak")
        shutil.copy2(roster_path, backup_file)
        print(f"-> Backup created: {os.path.basename(backup_file)}")
        return True
    except Exception as e:
        print(f"Warning: Could not create a backup of select.def. Reason: {e}")
        return False

def read_roster(roster_path, section_name):
    items = []
    if not os.path.exists(roster_path): return []
    try:
        with open(roster_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            in_section = False
            for line in f:
                line = line.strip()
                if not line or line.startswith(';'): continue
                if line.lower() == f'[{section_name.lower()}]': in_section = True; continue
                if line.startswith('['): in_section = False
                if in_section:
                    item_name = line.split(',')[0].strip()
                    if item_name and item_name.lower() != 'randomselect':
                        items.append(item_name)
    except Exception as e:
        print(f"Warning: Could not read {section_name}. Reason: {e}")
    return sorted(list(set(items)))

def write_roster(roster_path, char_list, stage_list):
    try:
        with open(roster_path, 'r', encoding='utf-8-sig', errors='ignore') as f: lines = f.readlines()
        
        with open(roster_path, 'w', encoding='utf-8') as f:
            in_chars, in_stages = False, False
            for line in lines:
                stripped_line = line.strip().lower()
                # Handle Characters section
                if stripped_line == '[characters]':
                    f.write(line)
                    for char in sorted(char_list): f.write(f"{char}\n")
                    f.write("randomselect\n")
                    in_chars = True
                elif in_chars and (stripped_line.startswith('[') or not line.strip()):
                    in_chars = False
                    f.write(line)
                # Handle ExtraStages section
                elif stripped_line == '[extrastages]':
                    f.write(line)
                    for stage in sorted(stage_list): f.write(f"{stage}\n")
                    in_stages = True
                elif in_stages and (stripped_line.startswith('[') or not line.strip()):
                    in_stages = False
                    f.write(line)
                # Write all other lines
                elif not in_chars and not in_stages:
                    f.write(line)
        return True
    except Exception as e:
        print(f"ERROR: Could not write to select.def. Reason: {e}")
        return False

def list_items(items, item_type):
    print(f"\n--- Currently Installed {item_type} ---")
    if not items:
        print(f"No {item_type.lower()} found in roster file."); return
    for i, item in enumerate(items, 1):
        # A bit of smart formatting for complex paths
        display_name = item.replace('\\', '/').split('/')[-1]
        full_path = "" if display_name == item else f"({item})"
        print(f"{i: >3}. {display_name.ljust(30)} {full_path}")

# --- Add/Delete functions refactored for new logic ---

def add_characters(roster_path, chars_folder, downloads_path, cleanup):
    # ... (This logic is fine, we just update the final call)
    archives = [f for f in os.listdir(downloads_path) if f.endswith(('.zip', '.rar', '.7z'))]
    if not archives: print("\nNo new character archives found."); return
    
    char_roster = read_roster(roster_path, "Characters")
    stage_roster = read_roster(roster_path, "ExtraStages")
    newly_added_chars = []

    for archive_name in archives:
        print(f"\n--- Installing: {archive_name} ---")
        archive_path = os.path.join(downloads_path, archive_name)
        temp_extract = os.path.join(get_base_path(), '_temp_extract')
        if os.path.exists(temp_extract): shutil.rmtree(temp_extract)
        os.makedirs(temp_extract)

        if not extract_archive(archive_path, temp_extract): continue
        char_folder_name = find_character_folder(temp_extract)
        if not char_folder_name: print("   ERROR: Could not identify a valid character folder. Skipping."); continue
        
        # Check against simple name
        if char_folder_name.lower() in [r.lower().split('\\')[0].split('/')[0] for r in char_roster]:
            print(f"   WARNING: '{char_folder_name}' seems to be already installed. Skipping."); continue

        source_path = os.path.join(temp_extract, char_folder_name)
        destination_path = os.path.join(chars_folder, char_folder_name)
        if os.path.exists(destination_path):
             print(f"   WARNING: Folder '{char_folder_name}' already exists. Skipping."); continue
        shutil.move(source_path, chars_folder)
        
        char_roster.append(char_folder_name)
        newly_added_chars.append(char_folder_name)
        print(f"   '{char_folder_name}' successfully installed.")
        
        if cleanup: os.remove(archive_path)
        shutil.rmtree(temp_extract)

    if newly_added_chars:
        print("\nUpdating select.def with new characters...")
        if backup_roster(roster_path):
            if write_roster(roster_path, char_roster, stage_roster):
                print("Roster updated successfully.")
            else:
                print("ERROR: Roster update failed. Your old select.def is safe.")
        else:
            print("ERROR: Backup failed. Roster will not be modified for safety.")

def delete_character(roster_path, chars_folder):
    char_roster = read_roster(roster_path, "Characters")
    stage_roster = read_roster(roster_path, "ExtraStages")
    list_items(char_roster, "Characters")
    if not char_roster: return
    try:
        choice = int(input("\nEnter number of character to delete (0 to cancel): "))
        if not 0 < choice <= len(char_roster): print("Invalid number. Deletion cancelled."); return
    except ValueError:
        print("Invalid input. Deletion cancelled."); return

    char_to_delete = char_roster[choice - 1]
    if input(f"PERMANENTLY DELETE '{char_to_delete}'? (y/n): ").lower() != 'y':
        print("Deletion cancelled."); return

    if backup_roster(roster_path):
        print(f"-> Removing '{char_to_delete}' from select.def...")
        char_roster.remove(char_to_delete)
        if write_roster(roster_path, char_roster, stage_roster):
            # Only delete the folder for simple entries to avoid mistakes
            simple_name = char_to_delete.split('\\')[0].split('/')[0]
            char_folder_path = os.path.join(chars_folder, simple_name)
            if os.path.isdir(char_folder_path):
                print(f"-> Deleting folder: {char_folder_path}")
                shutil.rmtree(char_folder_path)
            print(f"'{char_to_delete}' successfully deleted.")
        else:
            print("ERROR: Roster update failed. Your old select.def is safe.")
    else:
        print("ERROR: Backup failed. Roster will not be modified for safety.")

def add_stages(roster_path, stages_folder):
    print("\n--- Scanning for new stages ---")
    current_stages = read_roster(roster_path, "ExtraStages")
    # Get simple names for comparison, e.g. "stages/MyStage.def" -> "MyStage.def"
    current_stage_names = [s.replace('\\', '/').split('/')[-1] for s in current_stages]
    
    found_stages = [f for f in os.listdir(stages_folder) if f.lower().endswith('.def')]
    newly_added_stages = []

    for stage_file in found_stages:
        if stage_file.lower() not in current_stage_names:
            current_stages.append(f"stages/{stage_file}")
            newly_added_stages.append(stage_file)
    
    if not newly_added_stages:
        print("No new stages found.")
        return

    print(f"Found {len(newly_added_stages)} new stages:")
    for stage in newly_added_stages: print(f"  + {stage}")

    if backup_roster(roster_path):
        current_chars = read_roster(roster_path, "Characters")
        if write_roster(roster_path, current_chars, current_stages):
            print("\nRoster updated successfully with new stages.")
        else:
            print("ERROR: Roster update failed. Your old select.def is safe.")
    else:
        print("ERROR: Backup failed. Roster will not be modified for safety.")


# --- Helper functions (unchanged) ---
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
        elif archive_path.endswith('.7z'): with py7zr.SevenZipFile(archive_path, 'r') as s: s.extractall(path=extract_to)
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
    STAGES_FOLDER = os.path.join(GAME_PATH, 'stages')

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n MUGEN/IKEMEN GO Manager (select.def Edition) v5.0 ".center(60, "="))
        print("1. List Characters")
        print("2. Add New Character(s) from Downloads")
        print("3. Delete a Character")
        print("4. Scan and Add New Stages")
        print("5. Exit")
        choice = input("Please choose an option (1-5): ")
        
        if choice == '1':
            list_items(read_roster(roster_path, "Characters"), "Characters")
        elif choice == '2':
            add_characters(roster_path, CHARS_FOLDER, DOWNLOADS_PATH, config.get("CLEANUP_ARCHIVES_AFTER_ADD", True))
        elif choice == '3':
            delete_character(roster_path, CHARS_FOLDER)
        elif choice == '4':
            add_stages(roster_path, STAGES_FOLDER)
        elif choice == '5':
            print("Exiting."); break
        else:
            print("Invalid option, please try again.")
        
        input("\nPress Enter to return to the menu...")

if __name__ == "__main__":
    try:
        main_loop()
    except Exception as e:
        log_error_and_exit(e)
