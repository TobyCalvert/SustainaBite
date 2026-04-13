import pandas as pd
import json
import ast
import os

# --- Configurations ---
INGREDIENTS_JSON = "json files/food_database_complete.json"
RECIPES_PKL = "Data/archive/recipes_cache.pkl"
GUI_OUTPUT = "json files/gui_ingredients.json"


def standardize_ingredient(raw_name):
    words_to_remove = {"raw", "garden", "fresh", "organic", "cooked", "canned", "frozen", "diced", "chopped", "sliced",
                       "peeled", "whole", "premium", "natural", "fat", "free", "low", "large", "medium", "small",
                       "crushed", "minced", "masa", "relish", "unfortified", "or", "bottled",
        "frying", "rinsed", "slice", "nonsalted", "defatted",}
    clean_string = raw_name.replace("_", " ").replace("-", " ").lower()

    def singularize(word):
        if word in ["tomatoes", "potatoes"]: return word[:-2]
        if word.endswith("ies") and len(word) > 4: return word[:-3] + "y"
        if word.endswith("s") and not word.endswith("ss") and len(word) > 3: return word[:-1]
        return word

    processed_words = [singularize(word) for word in clean_string.split() if word not in words_to_remove]
    return " ".join(sorted(processed_words))


def build_gui_json():
    print("Building GUI ingredient database...")

    # 1. Get CO2 items
    with open(INGREDIENTS_JSON, "r") as f:
        raw_db = json.load(f)
    co2_standardized = {standardize_ingredient(k) for k in raw_db.keys()}

    # 2. Get all recipe items
    df_recipes = pd.read_pickle(RECIPES_PKL)
    all_recipe_ingredients = set()

    for _, row in df_recipes.iterrows():
        raw_ing = row.get('ingredients', [])
        if isinstance(raw_ing, str):
            try:
                raw_ing = ast.literal_eval(raw_ing)
            except:
                raw_ing = [raw_ing]
        for ing in raw_ing:
            std_ing = standardize_ingredient(str(ing))
            if std_ing: all_recipe_ingredients.add(std_ing)

    # 3. Combine and check
    gui_data = {}
    for ing in sorted(list(all_recipe_ingredients)):
        # True if it has CO2 data, False if it doesn't
        gui_data[ing] = ing in co2_standardized

    os.makedirs(os.path.dirname(GUI_OUTPUT), exist_ok=True)
    with open(GUI_OUTPUT, "w") as f:
        json.dump(gui_data, f, indent=4)

    print(f"✅ Created {GUI_OUTPUT} with {len(gui_data)} ingredients.")


if __name__ == "__main__":
    build_gui_json()