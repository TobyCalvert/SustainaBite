import json
import os

# --- CONFIGURATION ---
MAIN_DB_FILE = "../json files/food_database_complete.json"
SERVING_SIZE_FILE = "serving_estimates.json"


def apply_serving_sizes():
    if not os.path.exists(MAIN_DB_FILE):
        print(f"Error: Main database '{MAIN_DB_FILE}' not found.")
        return
    if not os.path.exists(SERVING_SIZE_FILE):
        print(f"Error: Serving size file '{SERVING_SIZE_FILE}' not found.")
        return

    print("Loading files...")
    with open(MAIN_DB_FILE, 'r') as f:
        main_db = json.load(f)

    with open(SERVING_SIZE_FILE, 'r') as f:
        serving_sizes = json.load(f)

    print(f"Merging {len(serving_sizes)} serving size estimates into main database...")

    updated_count = 0
    for key, serving_kg in serving_sizes.items():
        if key in main_db:
            main_db[key]["serving_kg"] = serving_kg
            updated_count += 1
        else:
            print(f"Warning: Key '{key}' in serving size list not found in main DB.")

    print(f"Merge complete. Updated {updated_count} items.")

    # Save back to main file
    with open(MAIN_DB_FILE, "w") as f:
        json.dump(main_db, f, indent=4)
    print(f"Successfully saved to {MAIN_DB_FILE}")


if __name__ == "__main__":
    apply_serving_sizes()