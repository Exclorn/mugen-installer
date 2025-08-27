import os
import shutil
import zipfile
import rarfile
import py7zr
import sys
import json
import subprocess

# ==============================================================================
# MUGEN/IKEMEN GO Character Manager v2.0
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
        "ENGINE_TYPE": "IKEMEN", # Can be "IKEMEN" or "MUGEN"
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
            return json.load(f)
    except (json.JSONDecodeError, KeyError):
        print(f"ERROR: '{config_path}' is corrupted or missing key values.")
        print("       Please fix it or delete it to regenerate a default file.")
        return None

# --- Character Roster Management ---

def get_roster_path(game_path, engine_type):
    if engine_type.upper() == "IKEMEN":
        return os.path.join(game_path, 'save', 'config.json')
    elif engine_type.upper() == "MUGEN":
        return os.path.join(game_path, 'data', 'select.def')
    return None

def read_roster(roster_path, engine_type):
    chars = []
    if engine_type.upper() == "IKEMEN":
        with open(roster_path, 'r') as f:
            config_data = json.load(f)
        for entry in config_data.get("Characters", []):
            # Extract folder name from "chars/FolderName/def.file"
            char_path = entry.get("char", "").replace('\\', '/')
            if char_path.startswith("chars/"):
                parts = char_path.split('/')
                if len(parts) > 1:
                    chars.append(parts[1])
    elif engine_type.upper() == "MUGEN":
        with open(roster_path, 'r') as f:
            in_chars_section = False
            for line in f:
                line = line.strip()
                if not line or line.startswith(';'): continue
                if line.lower() == '[characters]':
                    in_chars_section = True
                    continue
                if line.startswith('['):
                    in_chars_section = False
                if in_chars_section:
                    char_name = line.split(',')[0].split('\\')[0].strip()
                    chars.append(char_name)
    return sorted(list(set(chars))) # Return a sorted, unique list

def write_roster_ikemen(roster_path, chars_to_keep):
    with open(roster_path, 'r') as f:
        config_data = json.load(f)
    
    # Create a list of full "char" paths to keep
    full_paths_to_keep = []
    for entry in config_data.get("Characters", []):
        char_path = entry.get("char", "").replace('\\', '/')
        folder_name = char_path.split('/')[1] if char_path.startswith("chars/") and len(char_path.split('/')) > 1 else None
        if folder_name in chars_to_keep:
            full_paths_to_keep.append(entry)

    config_data["Characters"] = full_paths_to_keep
    with open(roster_path, 'w') as f:
        json.dump(config_data, f, indent=4)

def add_to_roster_ikemen(roster_path, char_folder_name, def_file_name):
    with open(roster_path, 'r') as f:
        config_data = json.load(f)
    
    new_entry = {"char": f"chars/{char_folder_name}/{def_file_name}"}
    
    if "Characters" not in config_data:
        config_data["Characters"] = []
    
    config_data["Characters"].append(new_entry)

    with open(roster_path, 'w') as f:
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
        choice = int(input("\nEnter the number of the character to delete (or 0 to cancel): "))
        if choice == 0 or choice > len(roster):
            print("Deletion cancelled.")
            return
    except ValueError:
        print("Invalid input. Deletion cancelled.")
        return

    char_to_delete = roster[choice - 1]
    
    confirm = input(f"Are you sure you want to PERMANENTLY DELETE '{char_to_delete}'? (y/n): ").lower()
    if confirm != 'y':
        print("Deletion cancelled.")
        return

    # 1. Remove from roster
    print(f"-> Removing '{char_to_delete}' from the roster...")
    roster.remove(char_to_delete)
    if engine_type.upper() == "IKEMEN":
        write_roster_ikemen(roster_path, roster)
    # Note: MUGEN select.def deletion is more complex, focusing on IKEMEN for now.
    
    # 2. Delete folder
    char_folder_path = os.path.join(chars_folder, char_to_delete)
    if os.path.isdir(char_folder_path):
        print(f"-> Deleting folder: {char_folder_path}")
        shutil.rmtree(char_folder_path)
    
    print(f"'{char_to_delete}' has been successfully deleted.")

def add_characters(roster, roster_path, engine_type, chars_folder, downloads_path, cleanup):
    archives = [f for f in os.listdir(downloads_path) if f.endswith(('.zip', '.rar', '.7z'))]
    if not archives:
        print("\nNo new character archives found in the downloads folder.")
        return

    print(f"\nFound {len(archives)} new character(s) to install.")
    for archive_name in archives:
        # Simplified installation logic from our previous script
        print(f"\n--- Installing: {archive_name} ---")
        archive_path = os.path.join(downloads_path, archive_name)
        temp_extract = os.path.join(get_base_path(), '_temp_extract')
        if os.path.exists(temp_extract): shutil.rmtree(temp_extract)
        os.makedirs(temp_extract)

        # Extract (using simplified helper)
        if not extract_archive(archive_path, temp_extract): continue
        
        # Find character folder
        char_folder_name = find_character_folder(temp_extract)
        if not char_folder_name:
            print("   ERROR: Could not identify a valid character folder. Skipping.")
            continue
        
        # Check for existing
        if char_folder_name in roster:
            print(f"   WARNING: '{char_folder_name}' is already installed. Skipping.")
            continue

        # Move
        source_path = os.path.join(temp_extract, char_folder_name)
        destination_path = os.path.join(chars_folder, char_folder_name)
        shutil.move(source_path, chars_folder)

        # Find .def file to add to roster
        def_file = find_def_file(destination_path)
        if not def_file:
            print(f"   WARNING: Could not find a .def file for '{char_folder_name}'. Folder moved, but not added to roster.")
            continue
        
        # Add to roster
        if engine_type.upper() == "IKEMEN":
            add_to_roster_ikemen(roster_path, char_folder_name, def_file)
            print(f"   '{char_folder_name}' successfully installed and added to roster.")
        
        if cleanup:
            os.remove(archive_path)

        shutil.rmtree(temp_extract)

def replace_character(roster, roster_path, engine_type, chars_folder, downloads_path, cleanup):
    # This is a combination of delete and add
    print("\n--- Replace a Character ---")
    print("This will delete the existing version and install a new version from an archive.")
    
    list_characters(roster, chars_folder)
    if not roster: return
    
    try:
        choice = int(input("\nEnter the number of the character to REPLACE (or 0 to cancel): "))
        if choice == 0 or choice > len(roster):
            print("Replacement cancelled.")
            return
    except ValueError:
        print("Invalid input. Replacement cancelled.")
        return

    char_to_replace = roster[choice - 1]
    
    archives = [f for f in os.listdir(downloads_path) if f.endswith(('.zip', '.rar', '.7z'))]
    if not archives:
        print("No archives found in downloads folder to replace with. Action cancelled.")
        return

    print("\nAvailable archives:")
    for i, archive in enumerate(archives, 1):
        print(f"{i}. {archive}")

    try:
        archive_choice = int(input(f"\nWhich archive contains the new version of '{char_to_replace}'? (number): "))
        if archive_choice == 0 or archive_choice > len(archives):
            print("Replacement cancelled.")
            return
    except ValueError:
        print("Invalid input. Replacement cancelled.")
        return

    archive_to_install = archives[archive_choice - 1]

    # Perform deletion
    print(f"\nStep 1: Deleting old version of '{char_to_replace}'...")
    roster.remove(char_to_replace)
    if engine_type.upper() == "IKEMEN":
        write_roster_ikemen(roster_path, roster)
    char_folder_path = os.path.join(chars_folder, char_to_replace)
    if os.path.isdir(char_folder_path):
        shutil.rmtree(char_folder_path)

    # Perform installation of the selected archive
    print(f"\nStep 2: Installing new version from '{archive_to_install}'...")
    add_characters(roster, roster_path, engine_type, chars_folder, downloads_path, cleanup)
    
    print(f"\nCharacter '{char_to_replace}' has been replaced.")

# --- Helper functions from previous script ---
def find_def_file(char_folder_path):
    char_folder_name = os.path.basename(char_folder_path)
    # Ideal case: a .def file with the same name as the folder
    if os.path.isfile(os.path.join(char_folder_path, f"{char_folder_name}.def")):
        return f"{char_folder_name}.def"
    # Fallback: find any .def file in the folder
    for file in os.listdir(char_folder_path):
        if file.lower().endswith('.def'):
            return file
    return None

def extract_archive(archive_path, extract_to):
    try:
        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as z: z.extractall(extract_to)
        elif archive_path.endswith('.rar'):
            with rarfile.RarFile(archive_path, 'r') as r: r.extractall(extract_to)
        elif archive_path.endswith('.7z'):
            with py7zr.SevenZipFile(archive_path, 'r') as s: s.extractall(extract_to)
        return True
    except Exception as e:
        print(f"   ERROR extracting {archive_path}: {e}")
        return False

def find_character_folder(base_path):
    contents = os.listdir(base_path)
    if not contents: return None
    if len(contents) == 1 and os.path.isdir(os.path.join(base_path, contents[0])):
        return contents[0]
    for item in contents:
        if os.path.isdir(os.path.join(base_path, item)) and find_def_file(os.path.join(base_path, item)):
            return item
    if contents and os.path.isdir(os.path.join(base_path, contents[0])):
        return contents[0] # Fallback to first folder
    return None

# ==============================================================================
# Main Program Loop
# ==============================================================================
def main():
    base_path = get_base_path()
    config_path = os.path.join(base_path, 'config.json')
    config = load_or_create_config(config_path)

    if config is None:
        input("\nPress Enter to exit.")
        return
    
    GAME_PATH = config.get("GAME_PATH")
    ENGINE_TYPE = config.get("ENGINE_TYPE", "IKEMEN")
    DOWNLOADS_PATH = config.get("DOWNLOADS_PATH")
    CLEANUP_ARCHIVES = config.get("CLEANUP_ARCHIVES_AFTER_ADD", True)
    
    roster_path = get_roster_path(GAME_PATH, ENGINE_TYPE)
    if not roster_path or not os.path.exists(roster_path):
        print(f"\nERROR: Could not find roster file for '{ENGINE_TYPE}' at '{GAME_PATH}'.")
        input("Press Enter to exit.")
        return

    CHARS_FOLDER = os.path.join(GAME_PATH, 'chars')

    while True:
        print("\n MUGEN/IKEMEN GO Character Manager ".center(50, "="))
        print("1. List all installed characters")
        print("2. Add new character(s) from downloads folder")
        print("3. Delete a character")
        print("4. Replace a character")
        print("5. Exit")
        choice = input("Please choose an option (1-5): ")
        
        # We need to re-read the roster each time in case it was modified
        current_roster = read_roster(roster_path, ENGINE_TYPE)

        if choice == '1':
            list_characters(current_roster, CHARS_FOLDER)
        elif choice == '2':
            add_characters(current_roster, roster_path, ENGINE_TYPE, CHARS_FOLDER, DOWNLOADS_PATH, CLEANUP_ARCHIVES)
        elif choice == '3':
            delete_character(current_roster, roster_path, ENGINE_TYPE, CHARS_FOLDER)
        elif choice == '4':
            replace_character(current_roster, roster_path, ENGINE_TYPE, CHARS_FOLDER, DOWNLOADS_PATH, CLEANUP_ARCHIVES)
        elif choice == '5':
            print("Exiting.")
            break
        else:
            print("Invalid option, please try again.")
        
        input("\nPress Enter to return to the menu...")
        # Clear screen for next menu display
        os.system('cls' if os.name == 'nt' else 'clear')


if __name__ == "__main__":
    # Check for unrar executable for rarfile
    if not shutil.which("unrar") and not os.path.exists("C:\\Program Files\\WinRAR\\UnRAR.exe"):
         print("WARNING: 'unrar' command not found in your system's PATH, and WinRAR not in default location.")
         print("         Extracting .rar files may fail. Please install WinRAR or unrar.")
    
    main()
