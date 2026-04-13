import pandas as pd
import json
import ast
import os

# --- CONFIGURATION ---
RECIPES_PKL = "Data/archive/recipes_cache.pkl"
OUTPUT_TAGS_FILE = "json files/unique_tags.json"


def extract_all_tags():
    print(f"--- 1. Loading recipes from {RECIPES_PKL} ---")

    if not os.path.exists(RECIPES_PKL):
        print("❌ Error: Recipe cache file not found. Check your file path.")
        return

    df_recipes = pd.read_pickle(RECIPES_PKL)
    unique_tags = set()

    print(f"--- 2. Scanning {len(df_recipes)} recipes for unique tags ---")

    for index, row in df_recipes.iterrows():
        raw_tags = row.get('tags', [])

        # Safely parse stringified lists
        if isinstance(raw_tags, str):
            try:
                raw_tags = ast.literal_eval(raw_tags)
            except:
                raw_tags = [raw_tags]
        elif not isinstance(raw_tags, (list, tuple)):
            continue  # Skip NaN or empty values

        # Clean and add to our master set
        for tag in raw_tags:
            clean_tag = str(tag).strip().lower()
            if clean_tag:
                unique_tags.add(clean_tag)

    # Sort alphabetically so they look nice in your UI dropdown
    sorted_tags = sorted(list(unique_tags))

    print(f"✅ Found {len(sorted_tags)} unique tags.")

    # --- 3. EXPORT ---
    print("\n--- 3. Saving to JSON ---")
    os.makedirs(os.path.dirname(OUTPUT_TAGS_FILE), exist_ok=True)

    with open(OUTPUT_TAGS_FILE, "w") as f:
        json.dump(sorted_tags, f, indent=4)

    print(f"✅ Successfully saved tag list to: {OUTPUT_TAGS_FILE}")
    print(f"   Sample tags: {sorted_tags[:15]}...")


if __name__ == "__main__":
    extract_all_tags()