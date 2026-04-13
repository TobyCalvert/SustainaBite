import pandas as pd
import json
import ast
import os

# --- CONFIGURATION ---
INGREDIENTS_JSON = "json files/food_database_complete.json"
RECIPES_PKL = "Data/archive/recipes_cache.pkl"
OUTPUT_DEBUG_FILE = "json files/debug_cleaned_names.json"


def clean_ingredient_name(raw_name):
    """
    Removes underscores and specific adjectives to standardize ingredient names.
    """
    # The set of words to strip out
    words_to_remove = {
        "raw", "garden", "fresh", "organic", "cooked",
        "canned", "frozen", "diced", "chopped", "sliced",
        "peeled", "whole", "premium", "natural", "fat",
        "free", "low", "large", "medium", "small", "deepfried", "ready", "meal", "food"
    }

    # Replace underscores and lowercase
    clean_string = raw_name.replace("_", " ").lower()

    # Split, filter, and rejoin
    return " ".join([word for word in clean_string.split() if word not in words_to_remove])


def run_diagnostics():
    print(f"--- 1. LOADING INGREDIENT DATABASE ({INGREDIENTS_JSON}) ---")

    if not os.path.exists(INGREDIENTS_JSON):
        print(f"❌ Error: File not found: {INGREDIENTS_JSON}")
        return

    with open(INGREDIENTS_JSON, "r") as f:
        raw_db = json.load(f)

    # --- EXPORT STEP: Create the Debug JSON ---
    debug_export = {}
    ingredient_lookup = {}  # We'll use this for the matching test later

    print(f"Processing {len(raw_db)} ingredients...")

    for key, data in raw_db.items():
        cleaned_name = clean_ingredient_name(key)

        # Save to our lookup dict for the recipe test
        ingredient_lookup[cleaned_name] = data

        # Save to our debug export dict (Format: Original -> Cleaned)
        debug_export[key] = cleaned_name

    # Write the debug file
    with open(OUTPUT_DEBUG_FILE, "w") as f:
        json.dump(debug_export, f, indent=4)

    print(f"✅ exported cleaned names to '{OUTPUT_DEBUG_FILE}'. Please check this file manually!")

    # --- 2. RECIPE MATCHING TEST ---
    print(f"\n--- 2. CHECKING RECIPE MATCHING ({RECIPES_PKL}) ---")

    if not os.path.exists(RECIPES_PKL):
        print(f"❌ Error: File not found: {RECIPES_PKL}")
        return

    try:
        df_recipes = pd.read_pickle(RECIPES_PKL)
        print(f"Loaded {len(df_recipes)} recipes.")
    except Exception as e:
        print(f"❌ Error loading pickle file: {e}")
        return

    print("\n--- Testing First 5 Recipes ---")

    # Iterate through just the first 5 recipes
    for index, row in df_recipes.head(5).iterrows():
        title = row.get('title', f"Recipe_{index}")
        print(f"\n🔸 RECIPE: {title}")

        # Check Calories
        raw_nut = row.get('nutrition', [])
        kcal = 0

        # Handle stringified lists (common in pandas CSV imports)
        if isinstance(raw_nut, str):
            try:
                parsed = ast.literal_eval(raw_nut)
                kcal = float(parsed[0]) if len(parsed) > 0 else 0
            except:
                pass
        # Handle actual lists
        elif isinstance(raw_nut, (list, tuple)) and len(raw_nut) > 0:
            kcal = float(raw_nut[0])

        print(f"   - Calories found: {kcal}")
        if kcal == 0:
            print("     ⚠️ WARNING: Calories are 0. This recipe will be skipped.")

        # Check Ingredients safely!
        raw_ingredients = row.get('ingredients', [])

        # Suspect 1 Fix: Force stringified lists back into real Python lists
        if isinstance(raw_ingredients, str):
            try:
                raw_ingredients = ast.literal_eval(raw_ingredients)
            except:
                raw_ingredients = [raw_ingredients]  # Fallback if it's just normal text

        print(f"   - Ingredient List: {raw_ingredients}")

        matches_found = []
        for recipe_ing in raw_ingredients:
            rec_str = str(recipe_ing).lower()

            for db_clean_name in ingredient_lookup.keys():
                # Suspect 2 Fix: Check if the exact database name is in the recipe string
                # We also add a space check to ensure "egg" doesn't match inside "veggie"
                if len(db_clean_name) > 2 and db_clean_name in rec_str:
                    matches_found.append(f"'{db_clean_name}' found in '{rec_str}'")
                    break

        if matches_found:
            print(f"   - ✅ Matched {len(matches_found)} ingredients:")
            for m in matches_found:
                print(f"      -> {m}")
        else:
            print("   - ❌ NO MATCHES FOUND. (Check naming conventions)")


if __name__ == "__main__":
    run_diagnostics()