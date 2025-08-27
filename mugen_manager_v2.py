import os
import json
import traceback
import sys
import shutil # Keep other imports in case we need them later

# ==============================================================================
# MUGEN/IKEMEN GO Manager v2.9 - Raw Diagnostic Tool
# This version's ONLY job is to dump the entire contents of the roster file.
# ==============================================================================

def log_error_and_exit(e):
    base_path = get_base_path()
    log_file_path = os.path.join(base_path, 'crash_log.txt')
    print(f"\nFATAL ERROR: A critical error occurred. Please check 'crash_log.txt' for details.")
    with open(log_file_path, 'w', encoding='utf-8') as f:
        f.write("MUGEN Manager v2.9 Crash Report\n=================================\n\n")
        f.write(traceback.format_exc())
    input("\nPress Enter to exit.")
    sys.exit(1)

def get_base_path():
    if getattr(sys, 'frozen', False): return os.path.dirname(sys.executable)
    else: return os.path.dirname(os.path.abspath(__file__))

def load_or_create_config(config_path):
    default_config = { "GAME_PATH": "C:/path/to/your/ikemen_go" }
    if not os.path.exists(config_path):
        print("-> config.json not found. Creating a default one now.")
        print(f"   Please edit '{config_path}' with your actual GAME_PATH and re-run.")
        with open(config_path, 'w', encoding='utf-8') as f: json.dump(default_config, f, indent=4)
        return None
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f: return json.load(f)
    except Exception as e:
        print(f"ERROR: Could not load '{config_path}'. {e}"); return None

def run_raw_dump(roster_path):
    print("\n--- Running Raw Roster Dump ---")
    output_file = os.path.join(get_base_path(), "roster_FULL_dump.txt")
    try:
        if not os.path.exists(roster_path):
            message = f"Error: Roster file does not exist at path:\n{roster_path}"
            print(message)
            with open(output_file, 'w', encoding='utf-8') as f: f.write(message)
            return

        with open(roster_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        
        message = f"--- Full Contents of {os.path.basename(roster_path)} ---\n\n"
        message += content
        
        with open(output_file, 'w', encoding='utf-8') as f: f.write(message)
        print(f"Success! The full contents of your roster file have been saved to:\n{output_file}")

    except Exception as e:
        message = f"A critical error occurred during diagnostics:\n\n{traceback.format_exc()}"
        print(message)
        with open(output_file, 'w', encoding='utf-8') as f: f.write(message)

def main_loop():
    base_path = get_base_path()
    config_path = os.path.join(base_path, 'config.json')
    config = load_or_create_config(config_path)

    if config is None:
        input("\nPress Enter to exit."); return
    
    GAME_PATH = config.get("GAME_PATH")
    roster_path = os.path.join(GAME_PATH, 'save', 'config.json')

    print("\n IKEMEN GO Roster Diagnostic Tool ".center(50, "="))
    print("This tool will read your IKEMEN GO roster file and save its")
    print("full contents to a text file for inspection.")
    
    run_raw_dump(roster_path)
    
    input("\nDiagnostics complete. Press Enter to exit.")

if __name__ == "__main__":
    try:
        main_loop()
    except Exception as e:
        log_error_and_exit(e)
