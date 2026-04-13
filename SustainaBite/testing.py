import pandas as pd
import os

RECIPES_PKL = "Data/archive/recipes_cache.pkl"
INTERACTIONS_PKL = "Data/archive/interactions_cache.pkl"
df_recipes = pd.read_pickle(RECIPES_PKL)
df_interactions = pd.read_pickle(INTERACTIONS_PKL)

OUTPUT_PKL = "Data/archive/combined_data.pkl"

# 1. Group the interactions by recipe_id to get one row per recipe
aggregated_ratings = df_interactions.groupby('recipe_id').agg({
    'rating': ['mean'] # Get average and number of ratings
}).reset_index()

# 2. Flatten the confusing column names created by aggregation
aggregated_ratings.columns = ['id', 'rating']

# 3. NOW merge this clean summary back to your recipes
final_data = pd.merge(
    df_recipes,
    aggregated_ratings,
    on='id',
    how='left' # Keep all recipes, even those with no ratings yet
)

os.makedirs(os.path.dirname(OUTPUT_PKL), exist_ok=True)
final_data.to_pickle(OUTPUT_PKL)
print(f"✅ Success! Optimized database saved to {OUTPUT_PKL}")

# Get the column headers as a list
column_headers = final_data.columns.tolist()

# Print the list
print(column_headers)