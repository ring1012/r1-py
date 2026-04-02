import subprocess
import os
import sys

def main():
    print("=== Running project build script ===")
    
    # 1. Sync dependencies with pywrangler
    print("Step 1: Syncing dependencies with pywrangler...")
    try:
        subprocess.run(["uv", "run", "pywrangler", "sync"], check=True)
    except Exception as e:
        print(f"Error syncing dependencies: {e}")
        # Try fallback to just workers-py if available as a command
        try:
            print("Trying fallback: workers-py sync...")
            subprocess.run(["workers-py", "sync"], check=True)
        except Exception as e2:
            print(f"Fallback failed: {e2}")
            sys.exit(1)

    # 2. Run the manual setup script for Pyodide
    print("Step 2: Setting up Pyodide-specific dependencies...")
    try:
        # Use absolute path to the script relative to this project root
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "setup_pyodide_deps.sh")
        if os.path.exists(script_path):
             subprocess.run(["bash", script_path], check=True)
        else:
             print(f"Setup script not found at {script_path}")
             sys.exit(1)
    except Exception as e:
        print(f"Error running setup script: {e}")
        sys.exit(1)

    print("=== Build completed successfully ===")

if __name__ == "__main__":
    main()
