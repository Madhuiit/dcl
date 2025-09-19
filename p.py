import json

# --- Configuration ---
file_to_count = 'players.json' 
# -------------------

try:
    # Open and read the JSON file
    with open(file_to_count, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # len() works for both lists (arrays) and dictionaries (objects)
    entry_count = len(data)

    print(f"✅ Success! The file '{file_to_count}' has {entry_count} entries.")

except FileNotFoundError:
    print(f"❌ Error: The file '{file_to_count}' was not found.")
except json.JSONDecodeError:
    print(f"❌ Error: The file '{file_to_count}' does not contain valid JSON.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")