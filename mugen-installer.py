import os
import shutil
import zipfile
import rarfile
import py7zr
import sys

# ==============================================================================
# SCRIPT CONFIGURATION - CHANGE THESE VALUES
# ==============================================================================

# 1. Set the full path to your MUGEN game folder.
#    Example (Windows): "C:/Users/YourUser/Games/mugen-1.1b1"
#    Example (macOS/Linux): "/home/youruser/games/mugen"
MUGEN_PATH = "F:\Games\The Queen Of Fighters" 

# 2. Set the path to the folder where you download your character archives.
#    The script will scan this folder for .zip, .rar, and .7z files.
DOWNLOADS_PATH = "F:\Games"

# 3. Set to True to delete the original .zip/.rar archive after a successful
#    installation. Set to False to keep it.
CLEANUP_ARCHIVES = True

# ==============================================================================
# DO NOT EDIT BELOW THIS LINE
# ==============================================================================

# --- Path Definitions ---
CHARS_FOLDER = os.path.join(MUGEN_PATH, 'chars')
DATA_FOLDER = os.path.join(MUGEN_PATH, 'data')
SELECT_DEF_PATH = os.path.join(DATA_FOLDER, 'select.def')
TEMP_EXTRACT_FOLDER = os.path.join(DOWNLOADS_PATH, '_temp_extract')

def validate_paths():
    """Checks if the configured paths are valid."""
    print("--- Validating Paths ---")
    if not os.path.isdir(MUGEN_PATH):
        print(f"ERROR: MUGEN path not found at '{MUGEN_PATH}'")
        sys.exit("Please correct the MUGEN_PATH in the script.")
    if not os.path.isdir(CHARS_FOLDER) or not os.path.isdir(DATA_FOLDER):
        print(f"ERROR: '{MUGEN_PATH}' does not look like a valid MUGEN folder (missing chars/ or data/).")
        sys.exit("Please ensure MUGEN_PATH is the root folder of your game.")
    if not os.path.isfile(SELECT_DEF_PATH):
        print(f"ERROR: select.def not found at '{SELECT_DEF_PATH}'")
        sys.exit("Critical file is missing from your MUGEN installation.")
    if not os.path.isdir(DOWNLOADS_PATH):
        print(f"INFO: Downloads folder '{DOWNLOADS_PATH}' not found. Creating it now.")
        os.makedirs(DOWNLOADS_PATH)
    print("All paths are valid. Starting process.\n")

def extract_archive(archive_path, extract_to):
    """Extracts a supported archive to a specified folder."""
    print(f"-> Extracting '{os.path.basename(archive_path)}'...")
    try:
        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
        elif archive_path.endswith('.rar'):
            with rarfile.RarFile(archive_path, 'r') as rar_ref:
                rar_ref.extractall(extract_to)
        elif archive_path.endswith('.7z'):
            with py7zr.SevenZipFile(archive_path, mode='r') as z_ref:
                z_ref.extractall(path=extract_to)
        else:
            return False
        print("   Extraction successful.")
        return True
    except Exception as e:
        print(f"   ERROR: Failed to extract archive. Reason: {e}")
        return False

def find_character_folder(base_path):
    """Finds the main character folder within the extracted files."""
    contents = os.listdir(base_path)
    
    # Best case: A single folder is in the root
    if len(contents) == 1 and os.path.isdir(os.path.join(base_path, contents[0])):
        char_folder = contents[0]
        # Check if it contains a .def file of the same name
        if os.path.isfile(os.path.join(base_path, char_folder, f"{char_folder}.def")):
            return char_folder

    # Search for a folder containing a .def file with the same name
    for item in contents:
        item_path = os.path.join(base_path, item)
        if os.path.isdir(item_path):
            def_file = os.path.join(item_path, f"{item}.def")
            if os.path.isfile(def_file):
                return item
                
    return None

def add_char_to_select_def(char_name):
    """Adds a character name to select.def if it's not already there."""
    print(f"-> Updating select.def for '{char_name}'...")
    
    with open(SELECT_DEF_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # Check if character is already present
    for line in lines:
        # Check for exact name or name with options (e.g., kfm, stages/stage.def)
        if line.strip().lower().startswith(char_name.lower()):
            print(f"   INFO: '{char_name}' is already present in select.def. Skipping.")
            return True

    # Find the [Characters] section and insert the new character
    new_lines = []
    in_chars_section = False
    inserted = False
    for line in lines:
        if line.strip().lower() == '[characters]':
            in_chars_section = True
            new_lines.append(line)
        elif in_chars_section and line.strip().startswith('['):
            # We've reached the next section (e.g., [ExtraStages])
            if not inserted:
                new_lines.append(f"{char_name}\n")
                inserted = True
            in_chars_section = False
            new_lines.append(line)
        else:
            new_lines.append(line)

    # If [Characters] is the last section, append at the end
    if in_chars_section and not inserted:
        new_lines.append(f"{char_name}\n")
        inserted = True

    if not inserted:
        print("   ERROR: Could not find the [Characters] section in select.def.")
        return False

    # Write the changes back to the file
    try:
        with open(SELECT_DEF_PATH, 'w', encoding='utf-8', errors='ignore') as f:
            f.writelines(new_lines)
        print("   select.def updated successfully.")
        return True
    except Exception as e:
        print(f"   ERROR: Could not write to select.def. Reason: {e}")
        return False


def main():
    """Main function to run the installer."""
    validate_paths()
    
    archives = [f for f in os.listdir(DOWNLOADS_PATH) if f.endswith(('.zip', '.rar', '.7z'))]

    if not archives:
        print("No new character archives found in the downloads folder.")
        return
        
    print(f"Found {len(archives)} character archive(s) to process.\n")

    for archive_name in archives:
        print(f"--- Processing: {archive_name} ---")
        archive_path = os.path.join(DOWNLOADS_PATH, archive_name)

        # 1. Extract to a temporary folder
        if os.path.exists(TEMP_EXTRACT_FOLDER):
            shutil.rmtree(TEMP_EXTRACT_FOLDER)
        os.makedirs(TEMP_EXTRACT_FOLDER)

        if not extract_archive(archive_path, TEMP_EXTRACT_FOLDER):
            continue
        
        # 2. Find the character folder
        char_folder_name = find_character_folder(TEMP_EXTRACT_FOLDER)
        if not char_folder_name:
            print("   ERROR: Could not identify a valid character folder in the archive. Skipping.")
            shutil.rmtree(TEMP_EXTRACT_FOLDER)
            continue
        
        print(f"   Identified character folder: '{char_folder_name}'")
        
        # 3. Check if character is already installed
        destination_path = os.path.join(CHARS_FOLDER, char_folder_name)
        if os.path.exists(destination_path):
            print(f"   WARNING: Character '{char_folder_name}' already exists in chars folder. Skipping.")
            shutil.rmtree(TEMP_EXTRACT_FOLDER)
            continue

        # 4. Move the character folder
        source_path = os.path.join(TEMP_EXTRACT_FOLDER, char_folder_name)
        shutil.move(source_path, CHARS_FOLDER)
        print(f"   Moved '{char_folder_name}' to chars folder.")

        # 5. Add to select.def
        if add_char_to_select_def(char_folder_name):
            # 6. Cleanup
            if CLEANUP_ARCHIVES:
                os.remove(archive_path)
                print(f"   Removed original archive: '{archive_name}'")
        
        shutil.rmtree(TEMP_EXTRACT_FOLDER)
        print(f"--- Finished processing: {archive_name} ---\n")

    print("=========================")
    print("All tasks completed.")


if __name__ == "__main__":

    main()
