import requests
import json
import time
import os
import re

# --- 1. CONFIGURATION ---
# PASTE YOUR KEY HERE
RAW_API_KEY = "3AE36XTBJH7SS3J96D6KXNAVZM"

# Safety clean
if "Bearer" in RAW_API_KEY:
    API_KEY_TOKEN = RAW_API_KEY.split("Bearer")[-1].strip()
else:
    API_KEY_TOKEN = RAW_API_KEY.strip()

HEADERS = {"Authorization": f"Bearer {API_KEY_TOKEN}"}

# API Endpoints
SEARCH_URL = "https://api.climatiq.io/search"
ESTIMATE_URL = "https://api.climatiq.io/data/v1/estimate"

OUTPUT_FILE = "json files/food_database.json"
METADATA_FILE = 'json files/METADATA.json'
MOCK_ITEMS_FILE = 'json files/MOCK_ITEMS.json'


# --- 2. HELPER FUNCTIONS ---
def load_json_file(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def to_snake_case(text):
    text = re.sub(r'[^\w\s]', '', text)
    return text.replace(" ", "_").lower()


# --- 3. DYNAMIC SEARCH LOGIC ---
def search_climatiq_ingredients():
    print("--- Searching Climatiq API (Source: CONCITO | Region: GB) ---")

    mapping = {}
    page = 1

    # STRICT FILTERING
    params = {
        "query": "food",
        "source": "CONCITO and 2-0 LCA",  # <--- FIXED: Strict Source
        "region": "GB",  # <--- FIXED: Region should work now
        "data_version": "^5",
        "results_per_page": 100,
        "page": page
    }

    while True:
        try:
            response = requests.get(SEARCH_URL, headers=HEADERS, params=params)

            if response.status_code != 200:
                print(f"  [API Error] {response.status_code} - {response.text}")
                break

            data = response.json()
            results = data.get("results", [])

            if not results:
                break

            for item in results:
                name = item.get("name")
                activity_id = item.get("id")

                # Convert to snake_case key
                key = to_snake_case(name)

                # Store unique items
                if key not in mapping:
                    mapping[key] = activity_id

            print(f"  Fetched page {page}... (Found {len(mapping)} items so far)")

            # Pagination check
            if page >= data.get("last_page", 1):
                break

            page += 1
            params["page"] = page
            time.sleep(0.2)

        except Exception as e:
            print(f"  [Search Crash] {e}")
            break

    print(f"--- Search Complete. Found {len(mapping)} specific items. ---")
    return mapping


# --- 4. CO2 FETCHING LOGIC ---
def fetch_co2_from_api(activity_id):
    """
    Fetches the CO2e for 1kg of the product.
    """
    payload = {
        "emission_factor": {
            "activity_id": activity_id,
            "source": "CONCITO and 2-0 LCA",  # Ensure consistency
            "region": "GB",
            "data_version": "^5"
        },
        "parameters": {"weight": 1, "weight_unit": "kg"}
    }

    try:
        response = requests.post(ESTIMATE_URL, headers=HEADERS, json=payload)
        if response.status_code == 200:
            return response.json().get("co2e", 0)
        else:
            # If strict fetch fails, try ID-only fallback
            fallback = {
                "emission_factor": {"activity_id": activity_id},
                "parameters": {"weight": 1, "weight_unit": "kg"}
            }
            retry = requests.post(ESTIMATE_URL, headers=HEADERS, json=fallback)
            if retry.status_code == 200:
                return retry.json().get("co2e", 0)
            return None
    except Exception as e:
        print(f"  [Network Error] {activity_id}: {e}")
        return None


# --- 5. MAIN BUILDER ---
def build_database():
    # 1. GENERATE MAPPING
    climatiq_mapping = search_climatiq_ingredients()

    metadata = load_json_file(METADATA_FILE)
    mock_items = load_json_file(MOCK_ITEMS_FILE)

    if not climatiq_mapping:
        print("Stopping: No items found. (Check if region 'GB' exists for this Source)")
        return

    print("--- Fetching Carbon Data ---")
    final_db = {}

    count = 0
    total = len(climatiq_mapping)

    for name, activity_id in climatiq_mapping.items():
        count += 1
        # Simple progress indicator
        if count % 10 == 0:
            print(f"  Processing {count}/{total}: {name}")

        co2_val = fetch_co2_from_api(activity_id)

        if co2_val is None:
            co2_val = 0.0

        if name in metadata:
            entry = metadata[name].copy()
            entry["id"] = activity_id
            entry["co2_per_kg"] = co2_val
            final_db[name] = entry
        else:
            # Create placeholder for Assumption Step
            entry = {
                "id": activity_id,
                "co2_per_kg": co2_val,
                "kcal": None,
                "protein": None,
                "fat": None,
                "carbs": None
            }
            final_db[name] = entry

        time.sleep(0.05)

    if mock_items:
        for name, data in mock_items.items():
            final_db[name] = data

    with open(OUTPUT_FILE, "w") as f:
        json.dump(final_db, f, indent=4)

    print(f"Done! Database saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    build_database()