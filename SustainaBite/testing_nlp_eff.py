import pandas as pd
import ast
from functools import lru_cache

# --- 1. CONFIGURATION ---
RECIPES_PKL = "Data/archive/recipes_cache.pkl"  # Make sure this points to your raw/uncached file


# --- 2. THE EXACT NLP STANDARDISER ---
@lru_cache(maxsize=None)
def singularize(word):
    if word in ["tomatoes", "potatoes"]: return word[:-2]
    if word.endswith("ies") and len(word) > 4: return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3: return word[:-1]
    return word


@lru_cache(maxsize=None)
def standardize_ingredient(raw_name):
    words_to_remove = {
        "raw", "garden", "fresh", "organic", "cooked", "canned", "frozen",
        "diced", "chopped", "sliced", "peeled", "whole", "premium", "natural",
        "fat", "free", "low", "large", "medium", "small", "crushed", "minced",
        "masa", "relish", "unfortified", "or", "bottled", "frying", "rinsed",
        "slice", "nonsalted", "defatted",
    }
    clean_string = raw_name.replace("_", " ").replace("-", " ").lower()
    processed_words = [singularize(word) for word in clean_string.split() if word not in words_to_remove]
    return " ".join(sorted(processed_words))


def safe_eval(val):
    if isinstance(val, str):
        try:
            return ast.literal_eval(val)
        except:
            return []
    if isinstance(val, list): return val
    return []


# --- 3. THE CALCULATOR ---
def calculate_efficiency():
    print(f"Loading database from {RECIPES_PKL}...")
    try:
        df = pd.read_pickle(RECIPES_PKL)
    except FileNotFoundError:
        print(f"Error: Could not find {RECIPES_PKL}. Please check the path.")
        return

    print("Extracting all raw ingredients...")
    # Convert stringified lists back to real lists
    df['ingredients'] = df['ingredients'].apply(safe_eval)

    # Flatten the list of lists into one giant list, then convert to a set to find the unique ones
    all_raw_ingredients = [item for sublist in df['ingredients'] for item in sublist]
    unique_raw = set(all_raw_ingredients)
    raw_count = len(unique_raw)

    print(f"Found {raw_count:,} unique raw ingredients. Standardising now...")

    # Pass every unique raw ingredient through the NLP pipeline
    unique_standardized = set()
    for ingredient in unique_raw:
        clean_name = standardize_ingredient(str(ingredient))
        if clean_name.strip():  # Only add it if it didn't get entirely erased by the stop-words
            unique_standardized.add(clean_name)

    clean_count = len(unique_standardized)

    # --- 4. THE MATH ---
    items_removed = raw_count - clean_count
    percentage_reduction = (items_removed / raw_count) * 100

    print("\n" + "=" * 50)
    print("📊 NLP STANDARDISATION RESULTS")
    print("=" * 50)
    print(f"Raw Unique Ingredients:       {raw_count:,}")
    print(f"Cleaned Unique Ingredients:   {clean_count:,}")
    print(f"Duplicate/Noise Items Erased: {items_removed:,}")
    print(f"Total Database Reduction:     {percentage_reduction:.2f}%")
    print("=" * 50)


if __name__ == "__main__":
    calculate_efficiency()