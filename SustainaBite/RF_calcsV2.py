import pandas as pd
import json
import ast
import os
from functools import lru_cache  # <-- NEW: Imports the speed hack

# --- 1. CONFIGURATION ---
INGREDIENTS_JSON = "json files/food_database_complete.json"
RECIPES_PKL = "Data/archive/recipes_cache.pkl"
PANTRY_JSON = "json files/pantry_data.json"
OUTPUT_TOP_50_FILE = "json files/top_50_low_carbon_recipes.json"

TOP_N = 50

# --- 2. TEXT PROCESSING  ---
@lru_cache(maxsize=None)  # <-- NEW: Memorizes results instantly
def singularize(word):
    if word in ["tomatoes", "potatoes"]: return word[:-2]
    if word.endswith("ies") and len(word) > 4: return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3: return word[:-1]
    return word

@lru_cache(maxsize=None)  # <-- NEW: Memorizes results instantly
def standardize_ingredient(raw_name):
    words_to_remove = {
        "raw", "garden", "fresh", "organic", "cooked",
        "canned", "frozen", "diced", "chopped", "sliced",
        "peeled", "whole", "premium", "natural", "fat",
        "free", "low", "large", "medium", "small", "crushed", "minced",
        "masa", "relish", "unfortified", "or", "bottled",
        "frying", "rinsed", "slice", "nonsalted", "defatted",
    }
    clean_string = raw_name.replace("_", " ").replace("-", " ").lower()
    processed_words = [singularize(word) for word in clean_string.split() if word not in words_to_remove]
    return " ".join(sorted(processed_words))


def check_tags(cell_data, required_tags):
    if isinstance(cell_data, str):
        try:
            actual_list = ast.literal_eval(cell_data)
        except:
            actual_list = [cell_data]
    elif isinstance(cell_data, (list, tuple)):
        actual_list = cell_data
    else:
        return False

    clean_tags = [str(t).strip().lower() for t in actual_list]
    return all(req.lower() in clean_tags for req in required_tags)

# --- 3. MAIN CALCULATOR ---
def calculate_top_recipes(required_tags=None, min_match_threshold=0.70, min_ingredients=6):
    print("--- 1. Loading & Standardizing Databases ---")
    if required_tags is None:
        required_tags = []

    if not os.path.exists(INGREDIENTS_JSON) or not os.path.exists(RECIPES_PKL):
        print("❌ Error: Missing data files. Check your file paths.")
        return

    # Load Carbon DB
    with open(INGREDIENTS_JSON, "r") as f:
        raw_db = json.load(f)

    db_standardized = {}
    for original_key, data in raw_db.items():
        std_name = standardize_ingredient(original_key)
        db_standardized[std_name] = data

    # Load and Standardize Pantry Data
    pantry_standardized = set()
    if os.path.exists(PANTRY_JSON):
        with open(PANTRY_JSON, "r") as f:
            try:
                pantry_data = json.load(f)
                for item in pantry_data:
                    std_pantry = standardize_ingredient(item.get("name", ""))
                    if std_pantry:
                        pantry_standardized.add(std_pantry)
            except Exception as e:
                print(f"⚠️ Warning: Could not read pantry data ({e}). Assuming empty pantry.")
    print(f"✅ Loaded {len(pantry_standardized)} items from your home pantry.")

    # Load Recipes
    df_recipes = pd.read_pickle(RECIPES_PKL)
    if required_tags:
        df_recipes = df_recipes[df_recipes['tags'].apply(lambda cell: check_tags(cell, required_tags))]

    valid_recipes = []

    print(f"--- 2. Scoring {len(df_recipes)} Recipes (Target: > {min_ingredients} ingredients, >= {min_match_threshold * 100}% coverage) ---")

    # FIXED: The duplicated loop is gone
    for index, row in df_recipes.iterrows():
        recipe_name = row.get('name', f"Recipe_{index}")

        # Safely extract ingredients
        raw_ingredients = row.get('ingredients', [])
        if isinstance(raw_ingredients, str):
            try:
                raw_ingredients = ast.literal_eval(raw_ingredients)
            except:
                raw_ingredients = [raw_ingredients]

        clean_raw_ingredients = [ing for ing in raw_ingredients if str(ing).strip()]
        total_ingredients_count = len(clean_raw_ingredients)

        if total_ingredients_count <= min_ingredients:
            continue

        # Safely extract Calories
        raw_nut = row.get('nutrition', [])
        recipe_kcal = 0
        if isinstance(raw_nut, str):
            try:
                parsed_nut = ast.literal_eval(raw_nut)
                recipe_kcal = float(parsed_nut[0]) if len(parsed_nut) > 0 else 0
            except:
                pass
        elif isinstance(raw_nut, (list, tuple)) and len(raw_nut) > 0:
            recipe_kcal = float(raw_nut[0])

        # Tracking variables for this specific recipe
        matched_count = 0
        total_co2 = 0
        matched_details = []
        unmatched_details = []

        # Check each ingredient
        for original_ing in clean_raw_ingredients:
            std_recipe_ing = standardize_ingredient(str(original_ing))

            if std_recipe_ing in pantry_standardized:
                matched_count += 1
                matched_details.append(f"{original_ing} -> {std_recipe_ing} [PANTRY: 0 CO2]")
            elif std_recipe_ing in db_standardized:
                db_data = db_standardized[std_recipe_ing]
                weight = db_data.get('serving_kg', 0)
                co2_val = db_data.get('co2_per_kg', 0)
                total_co2 += weight * co2_val
                matched_count += 1
                matched_details.append(f"{original_ing} -> {db_data.get('clean_name', std_recipe_ing)}")
            else:
                unmatched_details.append(original_ing)

        # --- THE 70% RULE CHECK ---
        match_ratio = matched_count / total_ingredients_count

        if match_ratio >= min_match_threshold:
            valid_recipes.append({
                "title": recipe_name,
                "total_co2": round(total_co2, 4),
                "kcal": recipe_kcal,
                "match_ratio": round(match_ratio, 3),
                "matched_count": matched_count,
                "total_count": total_ingredients_count,
                "matched_items": matched_details,
                "unmatched_items": unmatched_details
            })

    print(f"✅ Found {len(valid_recipes)} complex meals meeting the {min_match_threshold * 100}% threshold.")

    if not valid_recipes:
        print("❌ No recipes met the criteria.")
        return []

    # --- 3. SORT AND OUTPUT TOP 50 ---
    print(f"\n--- 3. Top {TOP_N} Lowest Carbon Recipes ---")

    valid_recipes.sort(key=lambda x: x['total_co2'])
    top_recipes = valid_recipes[:TOP_N]

    for i, recipe in enumerate(top_recipes, 1):
        print(f"\n{i}. {recipe['title']}")
        print(f"   CO2e: {recipe['total_co2']} kg | Kcal: {recipe['kcal']}")
        print(f"   Coverage: {recipe['match_ratio'] * 100:.1f}% ({recipe['matched_count']}/{recipe['total_count']})")
        print(f"   Matched: {', '.join([m.split(' -> ')[0] for m in recipe['matched_items'][:4]])}...")
        if recipe['unmatched_items']:
            print(f"   Missing: {', '.join(recipe['unmatched_items'][:3])}")

    return top_recipes


if __name__ == "__main__":
    calculate_top_recipes()