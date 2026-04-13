import pandas as pd
import json
import ast
import os

# --- 1. CONFIGURATION ---
INGREDIENTS_JSON = "json files/food_database_complete.json"
RECIPES_PKL = "Data/archive/recipes_cache.pkl"

MATCHED_OUTPUT_FILE = "json files/matched_pantry.json"
UNMATCHED_RECIPES_FILE = "json files/unmatched_recipes_report.json"
UNMATCHED_CARBON_FILE = "json files/unmatched_carbon_report.json"


def singularize(word):
    """A lightweight culinary plural-to-singular converter."""
    if word in ["tomatoes", "potatoes"]:
        return word[:-2]  # removes 'es'
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"  # berries -> berry
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]  # onions -> onion (but leaves 'glass' or 'grass' alone)
    return word


def standardize_ingredient(raw_name):
    """
    1. Removes adjectives.
    2. Converts to singular.
    3. Sorts words alphabetically to fix word-order issues.
    """
    words_to_remove = {
        "raw", "garden", "fresh", "organic", "cooked",
        "canned", "frozen", "diced", "chopped", "sliced",
        "peeled", "whole", "premium", "natural", "fat",
        "free", "low", "large", "medium", "small", "crushed", "minced",
        "masa", "relish", "unfortified", "or", "bottled",
        "frying", "rinsed", "slice", "nonsalted", "defatted",
    }

    # Replace underscores and hyphens with spaces, then lowercase
    clean_string = raw_name.replace("_", " ").replace("-", " ").lower()

    processed_words = []
    for word in clean_string.split():
        if word not in words_to_remove:
            processed_words.append(singularize(word))

    # Sort the words alphabetically (e.g., "wine white" becomes "white wine")
    return " ".join(sorted(processed_words))


def build_pantry_and_gap_analysis():
    print("--- 1. Loading & Cleaning Databases ---")

    if not os.path.exists(INGREDIENTS_JSON) or not os.path.exists(RECIPES_PKL):
        print("❌ Error: Missing data files.")
        return

    # Load Carbon DB
    with open(INGREDIENTS_JSON, "r") as f:
        raw_db = json.load(f)

    db_standardized_dict = {}
    for original_key in raw_db.keys():
        standard_name = standardize_ingredient(original_key)
        # We store the standard name as the key, and the original JSON key as the value
        db_standardized_dict[standard_name] = original_key

    # Load Recipes
    df_recipes = pd.read_pickle(RECIPES_PKL)

    print(f"--- 2. Extracting noun lists from {len(df_recipes)} recipes ---")

    # We will store a dictionary of { "Standardized Name": "Original Recipe String" }
    # This allows us to match using the clean math, but print the original text for you to read.
    recipe_ingredients_dict = {}

    for index, row in df_recipes.iterrows():
        raw_ingredients = row.get('ingredients', [])

        if isinstance(raw_ingredients, str):
            try:
                raw_ingredients = ast.literal_eval(raw_ingredients)
            except:
                raw_ingredients = [raw_ingredients]

        for ing in raw_ingredients:
            original_ing = str(ing).strip()
            if original_ing:
                # Standardize the recipe ingredient using the EXACT same logic as the database
                standard_ing = standardize_ingredient(original_ing)

                # Only add if it didn't completely disappear (e.g., if the ingredient was just "water")
                if standard_ing:
                    recipe_ingredients_dict[standard_ing] = original_ing

    print(f"✅ Found {len(recipe_ingredients_dict)} unique, standardized recipe ingredients.")
    print("--- 3. Running Smart Exact Match Analysis ---")

    matched_pantry = {}
    unmatched_recipes = {}
    successfully_matched_db_keys = set()

    # --- MATCHING LOOP ---
    for standard_recipe_ing, original_recipe_ing in recipe_ingredients_dict.items():

        # EXACT MATCH LOGIC (But using our standardized, sorted, singular strings)
        if standard_recipe_ing in db_standardized_dict:
            original_db_key = db_standardized_dict[standard_recipe_ing]

            # Save it nicely for the output file
            matched_pantry[original_recipe_ing] = f"Matched to DB: '{original_db_key}' (via '{standard_recipe_ing}')"
            successfully_matched_db_keys.add(standard_recipe_ing)
        else:
            unmatched_recipes[original_recipe_ing] = standard_recipe_ing

    # --- CHECK UNUSED CARBON DB ITEMS ---
    unmatched_carbon_db = {}
    for standard_db_ing, original_db_key in db_standardized_dict.items():
        if standard_db_ing not in successfully_matched_db_keys:
            unmatched_carbon_db[original_db_key] = standard_db_ing

    # --- 4. EXPORT RESULTS ---
    print("\n--- 4. Saving Files ---")

    with open(MATCHED_OUTPUT_FILE, "w") as f:
        # Sort alphabetically by the original recipe ingredient name
        sorted_matched = dict(sorted(matched_pantry.items()))
        json.dump({
            "Total_Matched": len(sorted_matched),
            "Matched_Items": sorted_matched
        }, f, indent=4)
    print(f"✅ Saved perfectly matched ingredients to: {MATCHED_OUTPUT_FILE}")

    with open(UNMATCHED_RECIPES_FILE, "w") as f:
        sorted_unmatched_recipes = dict(sorted(unmatched_recipes.items()))
        json.dump({
            "Note": "Format is 'Original Recipe String': 'How the code interpreted it'",
            "Total_Unmatched": len(sorted_unmatched_recipes),
            "Unmatched_Items": sorted_unmatched_recipes
        }, f, indent=4)
    print(f"✅ Saved un-matched recipe ingredients to: {UNMATCHED_RECIPES_FILE}")

    with open(UNMATCHED_CARBON_FILE, "w") as f:
        sorted_unmatched_carbon = dict(sorted(unmatched_carbon_db.items()))
        json.dump({
            "Note": "Format is 'Original DB Key': 'How the code interpreted it'",
            "Total_Unmatched": len(sorted_unmatched_carbon),
            "Unmatched_Items": sorted_unmatched_carbon
        }, f, indent=4)
    print(f"✅ Saved unused carbon ingredients to: {UNMATCHED_CARBON_FILE}")

    # --- SUMMARY ---
    match_rate = (len(matched_pantry) / len(recipe_ingredients_dict)) * 100
    db_utilization = (len(successfully_matched_db_keys) / len(db_standardized_dict)) * 100

    print(f"\n📊 SUMMARY:")
    print(
        f"   Recipe Ingredient Match Rate: {match_rate:.1f}% ({len(matched_pantry)}/{len(recipe_ingredients_dict)} found in DB)")
    print(
        f"   Carbon DB Utilization: {db_utilization:.1f}% ({len(successfully_matched_db_keys)}/{len(db_standardized_dict)} DB items used)")


if __name__ == "__main__":
    build_pantry_and_gap_analysis()