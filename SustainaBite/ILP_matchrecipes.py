import pandas as pd
import json
import os
import re
import ast  # Safer parsing than eval
import numpy as np
from sklearn.preprocessing import MultiLabelBinarizer
from scipy.sparse import csr_matrix

# --- CONFIGURATION ---
RECIPE_PKL = 'Data/archive/recipes_cache.pkl'
ILP_FILE = 'json files/ilp_output.json'
PANTRY_FILE = 'json files/pantry_data.json'


# ---------------------------------------------------------
# 1. ROBUST CLEANER (Improved Logic)
# ---------------------------------------------------------
def clean_ingredient_name(ingredient_name):
    """
    Standardizes ingredient names.
    Now uses the robust 'split-filter-join' method to handle noise words
    like 'raw spinach' -> 'spinach' correctly.
    """
    if not isinstance(ingredient_name, str):
        return ""

    # 1. Basic Normalize: Lowercase & Underscores
    name = ingredient_name.lower().replace("_", " ")

    # 2. Hard-coded aliases (Keep your existing map)
    replacements = {
        "courgette": "zucchini",
        "aubergine": "eggplant",
        "coriander": "cilantro",
        "mince": "ground beef",
        "jam": "jelly"
    }
    # Check exact match aliases first
    if name in replacements:
        name = replacements[name]

    # 3. Robust Noise Removal (The FIX)
    # We split into a list, filter out noise, and rejoin.
    # This catches "raw spinach" (no leading space) which .replace() misses.
    noise_words = {"raw", "garden", "fresh", "organic"}

    parts = name.split()
    cleaned_parts = [word for word in parts if word not in noise_words]
    name = " ".join(cleaned_parts)

    # 4. Remove non-letters (keep spaces)
    name = re.sub(r'[^a-z ]', '', name).strip()

    # 5. Singularize (Your existing logic, kept for consistency)
    if name.endswith("es"):
        name = name[:-2]
    elif name.endswith("s") and not name.endswith("ss"):
        name = name[:-1]

    return name


# ---------------------------------------------------------
# 2. MATRIX ENGINE
# ---------------------------------------------------------
def find_best_matches_matrix_method():
    print("--- 1. Loading & Vectorizing Database ---")

    # A. Load Data
    if os.path.exists(RECIPE_PKL):
        print(f"   Loading cached recipes from {RECIPE_PKL}...")
        df = pd.read_pickle(RECIPE_PKL)
    else:
        print("   Loading raw Excel file...")
        df = pd.read_excel('Data/archive/RAW_recipes.xlsx')

    # B. Fix Data Types (The FIX: ast.literal_eval)
    # Checks if the first item is a string before trying to convert
    if not df.empty and isinstance(df['ingredients'].iloc[0], str):
        print("   Converting stringified lists to Python lists...")
        df['ingredients'] = df['ingredients'].apply(ast.literal_eval)

    # C. Load Pantry
    pantry_set = set()
    if os.path.exists(PANTRY_FILE):
        with open(PANTRY_FILE, 'r') as f:
            raw = json.load(f)
            # Handle list vs dict format
            items = raw if isinstance(raw, list) else raw.get('ingredients', [])
            for item in items:
                val = item.get('name') if isinstance(item, dict) else item
                if val: pantry_set.add(clean_ingredient_name(val))

    print(f"   (Pantry Size: {len(pantry_set)})")

    # D. Clean & Vectorize DB
    print("   Cleaning recipe ingredients (applying singularization & noise removal)...")
    # Clean every ingredient in every recipe using the new robust function
    df['clean_ingredients'] = df['ingredients'].apply(lambda x: [clean_ingredient_name(i) for i in x])

    # Mask Pantry items out of the DB for search purposes
    if pantry_set:
        df['searchable_ingredients'] = df['clean_ingredients'].apply(lambda x: [i for i in x if i not in pantry_set])
    else:
        df['searchable_ingredients'] = df['clean_ingredients']

    # E. Create Sparse Matrix
    print("   Building Sparse Matrix...")
    mlb = MultiLabelBinarizer(sparse_output=True)

    # Fit on the cleaned, pantry-stripped ingredients
    X = mlb.fit_transform(df['searchable_ingredients'])

    # Save the vocabulary set for quick lookups
    vocab = set(mlb.classes_)
    print(f"   Matrix Built: {X.shape} (Recipes x Unique Ingredients)")

    # -----------------------------------------------------
    # 3. MATCHING
    # -----------------------------------------------------
    with open(ILP_FILE, 'r') as f:
        ilp_plan = json.load(f)

    results = {}

    print("\n--- 2. Running Matrix Search ---")

    for meal, ilp_ingredients in ilp_plan.items():
        if not ilp_ingredients: continue

        # 1. Clean ILP Target using the SAME function
        target_cleaned = [clean_ingredient_name(i) for i in ilp_ingredients]
        # Remove empty strings if cleaning stripped everything
        target_cleaned = [t for t in target_cleaned if t]

        # 2. Filter Valid Ingredients (Must exist in DB vocabulary)
        valid_target = [i for i in target_cleaned if i in vocab]
        missing_target = [i for i in target_cleaned if i not in vocab]

        print(f"\n[{meal.upper()}]")
        print(f"   Original ILP: {ilp_ingredients}")
        print(f"   Cleaned:      {target_cleaned}")

        if missing_target:
            print(f"   ⚠️ Ignored (Not in DB): {missing_target}")

        if not valid_target:
            print("   ❌ STOPPING: No matching ingredients found in database vocabulary.")
            continue

        # 3. Transform Target to Vector
        # Creates a (1, n_features) sparse matrix
        target_vector = mlb.transform([valid_target])

        # 4. MATRIX MULTIPLICATION (Dot Product)
        # Calculates intersection count for all recipes simultaneously
        # Result is a (n_recipes, 1) matrix
        overlap_counts = X.dot(target_vector.T).toarray().flatten()

        # 5. Calculate Score (Overlap Coefficient)
        # Score = Intersection / Size of Target
        # Uses len(target_cleaned) to punish if we asked for items the DB doesn't have
        if len(target_cleaned) > 0:
            scores = overlap_counts / len(target_cleaned)
        else:
            scores = np.zeros(overlap_counts.shape)

        # 6. Get Best Match
        best_idx = np.argmax(scores)
        best_score = scores[best_idx]

        if best_score > 0:
            best_recipe = df.iloc[best_idx]
            match_count = int(overlap_counts[best_idx])
            print(f"   🏆 Best Match: {best_recipe['name']}")
            print(f"      Score: {best_score:.2f} ({match_count}/{len(target_cleaned)} items)")

            results[meal] = best_recipe.to_dict()
        else:
            print("   ❌ No recipe overlaps found.")

    return results


if __name__ == "__main__":
    find_best_matches_matrix_method()