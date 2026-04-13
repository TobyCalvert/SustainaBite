import requests
import json
import time
import os
import re

# --- CONFIGURATION ---
API_KEY = "Bearer 3AE36XTBJH7SS3J96D6KXNAVZM"
HEADERS = {"Authorization": API_KEY}
ESTIMATE_URL = "https://api.climatiq.io/data/v1/estimate"

INPUT_FILE = "json files/food_database_filled.json"
OUTPUT_FILE = "json files/food_database_repaired.json"


# --- HELPER: IS IT A UUID? ---
def is_uuid(val):
    # Checks if the string looks like a UUID (8-4-4-4-12 hex chars)
    uuid_regex = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.match(uuid_regex, str(val)))


# --- API CALL ---
def fetch_co2_from_api(identifier, name):
    """
    Dynamically switches between 'id' (UUID) and 'activity_id' (String).
    """

    # 1. Build the Emission Factor dictionary
    emission_factor = {}

    if is_uuid(identifier):
        # If it's a UUID, we ONLY send the ID.
        # Region, Source, and Year are already baked into this unique ID.
        emission_factor["id"] = identifier
    else:
        # If it's a string (e.g. "food-type..."), we need filters.
        emission_factor["activity_id"] = identifier
        emission_factor["region"] = "GB"
        emission_factor["source"] = "CONCITO and 2-0 LCA"
        emission_factor["data_version"] = "^5"

    # 2. Construct Payload
    payload = {
        "emission_factor": emission_factor,
        "parameters": {"weight": 1, "weight_unit": "kg"}
    }

    try:
        response = requests.post(ESTIMATE_URL, headers=HEADERS, json=payload)

        if response.status_code == 200:
            return response.json().get("co2e", 0)

        else:
            # Print the actual error message from the API to help debug
            print(f"  [API Failure] {name}")
            print(f"    Code: {response.status_code}")
            print(f"    Msg:  {response.text}")  # <--- This will tell us exactly why
            return None

    except Exception as e:
        print(f"  [Network Error] {name}: {e}")
        return None


# --- MAIN LOGIC ---
def repair_database():
    if not os.path.exists(INPUT_FILE):
        print("Error: Input file not found.")
        return

    with open(INPUT_FILE, 'r') as f:
        data = json.load(f)

    updated_count = 0

    print(f"--- repairing {len(data)} items ---")

    for name, details in data.items():
        current_co2 = details.get("co2_per_kg", 0)
        identifier = details.get("id")

        # Skip mock items or items without IDs
        if not identifier or "mock" in str(identifier):
            continue

        # Only fetch if CO2 is missing/zero
        if current_co2 == 0.0:
            print(f"Fetching: {name} (ID: {identifier[:15]}...)")

            new_co2 = fetch_co2_from_api(identifier, name)

            if new_co2 is not None and new_co2 > 0:
                details["co2_per_kg"] = new_co2
                updated_count += 1
                print(f"  -> FIXED! {new_co2:.4f} kgCO2e")
            else:
                print(f"  -> Failed.")

            time.sleep(0.1)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=4)

    print(f"\nSuccess. Fixed {updated_count} items. Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    repair_database()