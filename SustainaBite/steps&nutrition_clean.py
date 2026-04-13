import pandas as pd
import ast
import os

INPUT_PKL = "Data/archive/combined_data.pkl"
OUTPUT_PKL = "Data/archive/recipes_optimized.pkl"  # We save to a new file!


def safe_eval(val):
    if isinstance(val, str):
        try:
            return ast.literal_eval(val)
        except:
            return []
    if isinstance(val, list):
        return val
    return []


def clean_database():
    print(f"Loading raw data from {INPUT_PKL}...")
    df = pd.read_pickle(INPUT_PKL)

    print("Cleaning 'steps' (Instructions)...")
    df['steps'] = df['steps'].apply(safe_eval)

    print("Cleaning 'nutrition'...")
    df['nutrition'] = df['nutrition'].apply(safe_eval)

    # Optional: You can do 'ingredients' and 'tags' here too to make your whole app faster!
    df['ingredients'] = df['ingredients'].apply(safe_eval)
    df['tags'] = df['tags'].apply(safe_eval)

    os.makedirs(os.path.dirname(OUTPUT_PKL), exist_ok=True)
    df.to_pickle(OUTPUT_PKL)
    print(f"✅ Success! Optimized database saved to {OUTPUT_PKL}")


if __name__ == "__main__":
    clean_database()