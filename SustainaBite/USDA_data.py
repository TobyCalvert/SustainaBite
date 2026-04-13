import requests
import json
import time
import os
import re

# --- CONFIGURATION ---
# GET YOUR KEY HERE: https://fdc.nal.usda.gov/api-key-signup.html
# Use "DEMO_KEY" if you don't have one, but it has strict rate limits.
USDA_API_KEY = "OfFxPr8uhmI8faXd7szTuYSm6QJgYbAH6W9ITfb1"
BASE_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

# Files
INPUT_FILE = "json files/climatiq_raw.json"
OUTPUT_FILE = "json files/food_database_complete.json"

SEARCH_OVERRIDES = {
    "Pizzasauce": "pizza sauce",
    "cider": "alcoholic cider",
    "Pastasauce": "Pasta sauce",
    sherry
    potatoes chips
    plaice
}

# --- HELPER FUNCTIONS ---
def clean_name_for_search(text):
    """
    Simplifies Climatiq names for better USDA matching.
    Example: 'Tomato (ripe - raw)' -> 'Tomato raw'
    """
    # Remove text inside parentheses (often contains processing info USDA doesn't like)
    text = re.sub(r'\([^)]*\)', '', text)
    # 2. Replace common separators with spaces
    text = text.replace("_", ",").replace("-", " ")
    # We use regex word boundaries \b to avoid replacing substrings (e.g. "mince" in "mincemeat")
    for problem, fix in SEARCH_OVERRIDES.items():
        if problem in text:
            # Check for whole word match to be safe, or just loose replace if generally safe
            # Using simple replace for robustness on concatenated words like "pizzasauce"
            text = text.replace(problem, fix)
    # Normalize spaces
    return " ".join(text.split())


def get_usda_nutrition(query):
    """
    Searches USDA for 1 result and extracts key nutrients per 1kg.
    """
    params = {
        "api_key": USDA_API_KEY,
        "query": query,
        "pageSize": 1,
        # We prefer "Foundation" or "SR Legacy" (standard reference) for raw ingredients
        "dataType": ["Foundation", "SR Legacy", "Survey Foods", "Branded Foods"]
    }

    try:
        response = requests.get(BASE_URL, params=params)

        # If forbidden/rate limited
        if response.status_code == 429:
            print("  [USDA Error] Rate limit exceeded. Waiting 10s...")
            time.sleep(10)
            return None
        if response.status_code != 200:
            print(f"  [USDA Error] {response.status_code}")
            return None

        data = response.json()

        # If no generic data found, try broader search (removing dataType filter)
        if not data.get("foods"):
            del params["dataType"]
            response = requests.get(BASE_URL, params=params)
            data = response.json()
            if not data.get("foods"):
                return None

        # Process the best match
        food = data["foods"][0]
        nutrients = food.get("foodNutrients", [])

        # USDA provides values per 100g. We need per 1kg (multiply by 10).
        result = {
            "kcal_per_kg": 0,
            "protein_per_kg": 0,
            "fat_per_kg": 0,
            "carbs_per_kg": 0
        }

        # USDA Nutrient IDs:
        # 1008 = Energy (Kcal)
        # 1003 = Protein
        # 1004 = Total lipid (fat)
        # 1005 = Carbohydrate

        for n in nutrients:
            nid = n.get("nutrientId")
            val = n.get("value", 0)

            if nid == 1008:
                result["kcal_per_kg"] = round(val * 10, 2)
            elif nid == 1003:
                result["protein_per_kg"] = round(val * 10, 2)
            elif nid == 1004:
                result["fat_per_kg"] = round(val * 10, 2)
            elif nid == 1005:
                result["carbs_per_kg"] = round(val * 10, 2)

        print(f"  Found: {food.get('description')[:30]}... ({result['kcal_per_kg']} kcal/kg)")
        return result

    except Exception as e:
        print(f"  [Error] {e}")
        return None


# --- MAIN LOGIC ---
def step2_process_nutrition():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found. Run Step 1 first.")
        return

    print("--- STEP 2: USDA NUTRITION BUILDER ---")
    print(f"Loading {INPUT_FILE}...")

    with open(INPUT_FILE, 'r') as f:
        data = json.load(f)

    final_db = {}
    skipped_count = 0
    processed_count = 0

    total_items = len(data)
    print(f"Scanning {total_items} items...")

    for key, item in data.items():
        # 1. FILTER: Skip items with 0 or null CO2e
        co2_val = item.get("co2_per_kg")
        if co2_val is None or co2_val == 0:
            skipped_count += 1
            # Optional: Uncomment to see what is being skipped
            # print(f"  Skipping {key} (Zero CO2)")
            continue

        # 2. PREPARE SEARCH
        name = item.get("clean_name", key)
        search_query = clean_name_for_search(name)

        print(f"[{processed_count + 1}] Processing '{search_query}'...", end="", flush=True)

        # 3. FETCH NUTRITION
        nutri_data = get_usda_nutrition(search_query)

        if nutri_data:
            item.update(nutri_data)
        else:
            print("  No match found (keeping defaults).")

        # Add to final DB
        final_db[key] = item
        processed_count += 1

        # USDA Demo key rate limit is strict (approx 30-50 calls/hour or burst limits)
        # Increase sleep if you get 429 errors.
        time.sleep(0.5)

        # 4. SAVE
    print("-" * 30)
    print(f"Processing Complete.")
    print(f"  - Total processed: {processed_count}")
    print(f"  - Skipped (0 CO2): {skipped_count}")
    print(f"Saving to {OUTPUT_FILE}...")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(final_db, f, indent=4)

    print("Done!")


if __name__ == "__main__":
    step2_process_nutrition()