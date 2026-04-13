import pandas as pd
import os
import xgboost as xgb
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from gensim.models import Word2Vec
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error

# Define filenames
raw_file_recipes = 'Data/archive/RAW_recipes.xlsx'
cache_file_recipes = 'Data/archive/recipes_cache.pkl'
raw_file_interactions = 'Data/archive/RAW_interactions.xlsx'
cache_file_interactions = 'Data/archive/interactions_cache.pkl'

# Check if the fast cache file exists
if os.path.exists(cache_file_recipes):
    print("Loading from fast cache...")
    data_recipes = pd.read_pickle(cache_file_recipes)
else:
    print("Reading slow recipes Excel file (this happens only once)...")
    data_recipes = pd.read_excel(raw_file_recipes)
    print("Saving to cache...")
    data_recipes.to_pickle(cache_file_recipes)

if os.path.exists(cache_file_interactions):
    print("Loading from fast cache...")
    data_interactions = pd.read_pickle(cache_file_interactions)
else:
    print("Reading slow interactions Excel file (this happens only once)...")
    data_interactions = pd.read_excel(raw_file_interactions)
    print("Saving to cache...")
    data_interactions.to_pickle(cache_file_interactions)

print("Data loaded!")

data_interactions.drop(data_interactions[data_interactions['rating']==0].index, inplace=True)

# 1. Group the interactions by recipe_id to get one row per recipe
aggregated_ratings = data_interactions.groupby('recipe_id').agg({
    'rating': ['mean', 'count']
}).reset_index()

# 2. Flatten columns
aggregated_ratings.columns = ['id', 'average_rating', 'rating_count']

# 3. Merge this clean summary back to recipes
final_data = pd.merge(
    data_recipes,
    aggregated_ratings,
    on='id',
    how='left'
)

# 4. Fill NaN values (recipes with 0 reviews)
final_data['average_rating'] = final_data['average_rating'].fillna(0)
final_data['rating_count'] = final_data['rating_count'].fillna(0)

# ---------------------------------------------------------
# 1. PREPARE DATA FOR WORD2VEC
# ---------------------------------------------------------
print("Parsing ingredient lists...")
recipes_ingredients = final_data['ingredients'].apply(eval).tolist()

# ---------------------------------------------------------
# 2. TRAIN THE WORD2VEC MODEL
# ---------------------------------------------------------
print("Training Word2Vec model on your ingredients...")
w2v_model = Word2Vec(
    sentences=recipes_ingredients,
    vector_size=100,
    window=5,
    min_count=5,
    workers=4,
    seed=42
)

# ---------------------------------------------------------
# 3. VECTORIZE RECIPES
# ---------------------------------------------------------
def get_recipe_vector(ingredient_list, model):
    valid_vectors = [model.wv[word] for word in ingredient_list if word in model.wv]
    if len(valid_vectors) == 0:
        return np.zeros(model.vector_size)
    return np.mean(valid_vectors, axis=0)

print("Vectorizing all recipes...")
recipe_vectors = [get_recipe_vector(recipe, w2v_model) for recipe in recipes_ingredients]

X_embeddings = pd.DataFrame(recipe_vectors)
X_embeddings.columns = [f'vec_{i}' for i in range(100)]

# ---------------------------------------------------------
# 4. PREPARE FINAL INPUTS (X)
# ---------------------------------------------------------
final_data.reset_index(drop=True, inplace=True)
X_embeddings.reset_index(drop=True, inplace=True)

nutrition_df = final_data['nutrition'].str.strip('[]').str.split(', ', expand=True)
nutrition_df.columns = ['calories', 'total_fat', 'sugar', 'sodium', 'protein', 'sat_fat', 'carbs']
nutrition_df = nutrition_df.astype(float)

metadata_df = final_data[['minutes', 'n_steps']].copy()

X_final = pd.concat([X_embeddings, metadata_df, nutrition_df], axis=1)

print(f"New Feature Count: {X_final.shape[1]}")
X = X_final
y = final_data['average_rating']

# --- THE FIX: FILTER OUT UNRATED (0 STAR) RECIPES ---
print("\nFiltering out unrated (0-star) recipes from training data...")
# Create a mask of recipes that actually have a human rating
rated_mask = final_data['average_rating'] > 0

# Create specific Training/Testing sets that ONLY contain rated recipes
X_model = X[rated_mask]
y_model = y[rated_mask]

print(f"Total Recipes: {len(X)} | Recipes with Ratings used for training: {len(X_model)}")

# ---------------------------------------------------------
# 2. SPLIT DATA (Train / Validate / Test)
# ---------------------------------------------------------
# Notice we are now splitting X_model and y_model, NOT X and y!
X_train, X_temp, y_train, y_temp = train_test_split(
    X_model, y_model, test_size=0.3, random_state=42
)

X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.5, random_state=42
)

print(f"Training sets: {X_train.shape}")
print(f"Validation sets: {X_val.shape}")
print(f"Test sets: {X_test.shape}")

# ---------------------------------------------------------
# 3. CONFIGURE & TRAIN XGBOOST
# ---------------------------------------------------------
model = xgb.XGBRegressor(
    objective='reg:squarederror',
    n_estimators=1000,
    learning_rate=0.05,
    max_depth=6,
    early_stopping_rounds=50,
    random_state=42,
    device="cuda",
    tree_method="hist"
)

print("Starting training...")
# Calculate weights, but ensure they map correctly to the training index
weights = np.log1p(final_data['rating_count'])

model.fit(
    X_train, y_train,
    sample_weight=weights.loc[X_train.index], # Aligned perfectly with filtered data
    eval_set=[(X_train, y_train), (X_val, y_val)],
    verbose=100
)

# ---------------------------------------------------------
# 4. EVALUATE ON TEST SET & PLOT RESULTS
# ---------------------------------------------------------
predictions = model.predict(X_test)
mae = mean_absolute_error(y_test, predictions)
mse = mean_squared_error(y_test, predictions)

print("------------------------------------------------")
print(f"Mean Absolute Error (MAE): {mae:.4f}")
print("------------------------------------------------")

# Define the plotting function
def plot_xgboost_evaluation(y_test, y_pred, xgb_model, X_test):
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    residuals = y_test - y_pred

    # Calculate and print metrics BEFORE showing the graph
    mse = np.mean(residuals ** 2)
    rmse = np.sqrt(mse)
    print(f"Mean Squared Error (MSE): {mse:.4f}")
    print(f"Root Mean Squared Error (RMSE): {rmse:.4f}")

    # --- Graph 1 ---
    axes[0].scatter(y_test, y_pred, alpha=0.3, color='#2E86C1')
    # FIX: Changed 'k--' to '--' so it doesn't conflict with the red color
    axes[0].plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], '--', lw=2, color='#E74C3C')
    axes[0].set_xlabel('Actual Recipe Ratings')
    axes[0].set_ylabel('Predicted Ratings')
    axes[0].set_title('Graph 1: Actual vs. Predicted Ratings')

    # --- Graph 2 ---
    axes[1].scatter(y_pred, residuals, alpha=0.3, color='#27AE60')
    axes[1].axhline(y=0, color='#E74C3C', linestyle='--', lw=2)
    axes[1].set_xlabel('Predicted Ratings')
    axes[1].set_ylabel('Residuals (Actual - Predicted)')
    axes[1].set_title('Graph 2: Residual Analysis')

    # --- Graph 3 ---
    importance = xgb_model.feature_importances_
    sorted_idx = np.argsort(importance)[-10:]
    features = X_test.columns[sorted_idx]

    axes[2].barh(range(10), importance[sorted_idx], align='center', color='#8E44AD')
    axes[2].set_yticks(range(10))
    axes[2].set_yticklabels(features)
    axes[2].set_xlabel('Relative Importance')
    axes[2].set_title('Graph 3: Top 10 Feature Importances')

    plt.tight_layout()

    # This will pause the script. Close the window to let the script finish saving!
    print("Close the graph window to finish saving the database...")
    plt.show()

# --- CALL THE PLOT FUNCTION HERE ---
# Note the corrected variable names: 'predictions' and 'model'
plot_xgboost_evaluation(y_test, predictions, model, X_test)


# Save the Word2Vec model
w2v_model.save("Data/archive/ingredient_w2v.model")
print("✅ Word2Vec model saved successfully!")

# ---------------------------------------------------------
# 5. FILL THE GAPS & SAVE THE FINAL DATABASE
# ---------------------------------------------------------
print("\n--- Filling Missing Ratings ---")
missing_mask = final_data['average_rating'] == 0
print(f"Predicting AI ratings for {missing_mask.sum()} unrated recipes...")

predicted_ratings = model.predict(X[missing_mask])
predicted_ratings = np.clip(predicted_ratings, 1.0, 5.0)

final_data.loc[missing_mask, 'average_rating'] = np.round(predicted_ratings, 1)
final_data['is_predicted_rating'] = missing_mask
final_data.rename(columns={'average_rating': 'rating'}, inplace=True)

# ---------------------------------------------------------
# 6. CLEAN FORMATTING FOR STREAMLIT APP
# ---------------------------------------------------------
print("\n--- Cleaning Data for the App ---")
import ast

def safe_eval(val):
    if isinstance(val, str):
        try: return ast.literal_eval(val)
        except: return []
    if isinstance(val, list): return val
    return []

final_data['steps'] = final_data['steps'].apply(safe_eval)
final_data['nutrition'] = final_data['nutrition'].apply(safe_eval)
final_data['ingredients'] = final_data['ingredients'].apply(safe_eval)
final_data['tags'] = final_data['tags'].apply(safe_eval)

OUTPUT_PKL = "Data/archive/recipes_optimized.pkl"
os.makedirs(os.path.dirname(OUTPUT_PKL), exist_ok=True)
final_data.to_pickle(OUTPUT_PKL)

print(f"✅ Success! Gap-free, fully cleaned database saved to {OUTPUT_PKL}")