import pandas as pd
import os
import xgboost as xgb
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from gensim.models import Word2Vec
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.feature_extraction.text import TfidfVectorizer
import ast

# Define filenames
raw_file_recipes = 'Data/archive/RAW_recipes.xlsx'
cache_file_recipes = 'Data/archive/recipes_cache.pkl'
raw_file_interactions = 'Data/archive/RAW_interactions.xlsx'
cache_file_interactions = 'Data/archive/interactions_cache.pkl'

# --- DATA LOADING (Unchanged) ---
if os.path.exists(cache_file_recipes):
    print("Loading from fast cache...")
    data_recipes = pd.read_pickle(cache_file_recipes)
else:
    print("Reading slow recipes Excel file...")
    data_recipes = pd.read_excel(raw_file_recipes)
    data_recipes.to_pickle(cache_file_recipes)

if os.path.exists(cache_file_interactions):
    print("Loading from fast cache...")
    data_interactions = pd.read_pickle(cache_file_interactions)
else:
    print("Reading slow interactions Excel file...")
    data_interactions = pd.read_excel(raw_file_interactions)
    data_interactions.to_pickle(cache_file_interactions)

data_interactions.drop(data_interactions[data_interactions['rating'] == 0].index, inplace=True)

aggregated_ratings = data_interactions.groupby('recipe_id').agg({
    'rating': ['mean', 'count']
}).reset_index()
aggregated_ratings.columns = ['id', 'average_rating', 'rating_count']

final_data = pd.merge(data_recipes, aggregated_ratings, on='id', how='left')
final_data['average_rating'] = final_data['average_rating'].fillna(0)
final_data['rating_count'] = final_data['rating_count'].fillna(0)

# ---------------------------------------------------------
# 1. PREPARE DATA & TF-IDF (UPGRADE #3)
# ---------------------------------------------------------
print("Parsing ingredient lists...")
recipes_ingredients = final_data['ingredients'].apply(eval).tolist()

print("Calculating TF-IDF weights for ingredients...")
# Convert list of ingredients to space-separated strings for TF-IDF
sentences_as_strings = [' '.join(recipe).replace(" ", "_") for recipe in recipes_ingredients]
tfidf = TfidfVectorizer(min_df=5)
tfidf.fit(sentences_as_strings)
# Create a dictionary mapping the ingredient to its importance weight
tfidf_dict = dict(zip(tfidf.get_feature_names_out(), tfidf.idf_))

print("Training Word2Vec model on your ingredients...")
w2v_model = Word2Vec(sentences=recipes_ingredients, vector_size=100, window=5, min_count=5, workers=4, seed=42)


# ---------------------------------------------------------
# 2. VECTORIZE RECIPES WITH TF-IDF WEIGHTS
# ---------------------------------------------------------
def get_tfidf_recipe_vector(ingredient_list, model, tfidf_weights):
    valid_vectors = []
    weights = []
    for word in ingredient_list:
        clean_word = word.replace(" ", "_")
        if word in model.wv and clean_word in tfidf_weights:
            valid_vectors.append(model.wv[word])
            weights.append(tfidf_weights[clean_word])

    if len(valid_vectors) == 0:
        return np.zeros(model.vector_size)

    # Calculate the WEIGHTED average instead of a simple average
    return np.average(valid_vectors, axis=0, weights=weights)


print("Vectorizing all recipes with TF-IDF weighting...")
recipe_vectors = [get_tfidf_recipe_vector(recipe, w2v_model, tfidf_dict) for recipe in recipes_ingredients]

X_embeddings = pd.DataFrame(recipe_vectors)
X_embeddings.columns = [f'vec_{i}' for i in range(100)]

# ---------------------------------------------------------
# 3. PREPARE FINAL INPUTS (X)
# ---------------------------------------------------------
final_data.reset_index(drop=True, inplace=True)
X_embeddings.reset_index(drop=True, inplace=True)

nutrition_df = final_data['nutrition'].str.strip('[]').str.split(', ', expand=True)
nutrition_df.columns = ['calories', 'total_fat', 'sugar', 'sodium', 'protein', 'sat_fat', 'carbs']
nutrition_df = nutrition_df.astype(float)

metadata_df = final_data[['minutes', 'n_steps']].copy()

X_final = pd.concat([X_embeddings, metadata_df, nutrition_df], axis=1)
X = X_final
y = final_data['average_rating']

# ---------------------------------------------------------
# 4. SPLIT DATA & BALANCE CLASSES (UPGRADE #2)
# ---------------------------------------------------------
X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.3, random_state=42)
X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42)

print("\nBalancing the Training Data to remove 5-star bias...")
# Recombine X and y temporarily to filter them
train_df = pd.concat([X_train, y_train], axis=1)
# Create a rounded rating to use as a "class" bin
train_df['rating_bin'] = np.round(train_df['average_rating'])

# Cap the maximum number of recipes per rating bin to match the median class size
cap = int(train_df['rating_bin'].value_counts().median())
balanced_train_df = train_df.groupby('rating_bin').apply(lambda x: x.sample(min(len(x), cap))).reset_index(drop=True)

y_train_balanced = balanced_train_df['average_rating']
X_train_balanced = balanced_train_df.drop(['average_rating', 'rating_bin'], axis=1)

print(f"Old Training Size: {len(X_train)} | New Balanced Training Size: {len(X_train_balanced)}")

# ---------------------------------------------------------
# 5. GRID SEARCH HYPERPARAMETER TUNING (UPGRADE #5)
# ---------------------------------------------------------
print("\nStarting Grid Search Tuning (This will take a while)...")

# Define the combinations you want to test
param_grid = {
    'max_depth': [4, 6],
    'learning_rate': [0.05, 0.1],
    'n_estimators': [200, 500]
}

base_model = xgb.XGBRegressor(
    objective='reg:squarederror',
    random_state=42,
    device="cuda",  # Change to "cpu" if you don't have a GPU set up
    tree_method="hist"
)

# Test all combinations across 3 folds
grid_search = GridSearchCV(
    estimator=base_model,
    param_grid=param_grid,
    scoring='neg_mean_absolute_error',
    cv=3,
    verbose=1
)

grid_search.fit(X_train_balanced, y_train_balanced)

print(f"✅ Best parameters found: {grid_search.best_params_}")
best_model = grid_search.best_estimator_

# ---------------------------------------------------------
# 6. EVALUATE ON TEST SET & PLOT RESULTS
# ---------------------------------------------------------
predictions = best_model.predict(X_test)
mae = mean_absolute_error(y_test, predictions)
mse = mean_squared_error(y_test, predictions)

print("------------------------------------------------")
print(f"Mean Absolute Error (MAE): {mae:.4f}")
print(f"Root Mean Squared Error (RMSE): {np.sqrt(mse):.4f}")
print("------------------------------------------------")


def plot_xgboost_evaluation(y_test, y_pred, xgb_model, X_test):
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    residuals = y_test - y_pred

    axes[0].scatter(y_test, y_pred, alpha=0.3, color='#2E86C1')
    axes[0].plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], '--', lw=2, color='#E74C3C')
    axes[0].set_xlabel('Actual Recipe Ratings')
    axes[0].set_ylabel('Predicted Ratings')
    axes[0].set_title('Graph 1: Actual vs. Predicted Ratings')

    axes[1].scatter(y_pred, residuals, alpha=0.3, color='#27AE60')
    axes[1].axhline(y=0, color='#E74C3C', linestyle='--', lw=2)
    axes[1].set_xlabel('Predicted Ratings')
    axes[1].set_ylabel('Residuals (Actual - Predicted)')
    axes[1].set_title('Graph 2: Residual Analysis')

    importance = xgb_model.feature_importances_
    sorted_idx = np.argsort(importance)[-10:]
    features = X_test.columns[sorted_idx]

    axes[2].barh(range(10), importance[sorted_idx], align='center', color='#8E44AD')
    axes[2].set_yticks(range(10))
    axes[2].set_yticklabels(features)
    axes[2].set_xlabel('Relative Importance')
    axes[2].set_title('Graph 3: Top 10 Feature Importances')

    plt.tight_layout()
    print("Close the graph window to finish saving the database...")
    plt.show()


# Call the plot function
plot_xgboost_evaluation(y_test, predictions, best_model, X_test)

# ---------------------------------------------------------
# 7. FILL THE GAPS & SAVE THE FINAL DATABASE
# ---------------------------------------------------------
w2v_model.save("Data/archive/ingredient_w2v.model")
print("✅ Word2Vec model saved successfully!")

print("\n--- Filling Missing Ratings ---")
missing_mask = final_data['average_rating'] == 0
predicted_ratings = best_model.predict(X[missing_mask])
predicted_ratings = np.clip(predicted_ratings, 1.0, 5.0)

final_data.loc[missing_mask, 'average_rating'] = np.round(predicted_ratings, 1)
final_data['is_predicted_rating'] = missing_mask
final_data.rename(columns={'average_rating': 'rating'}, inplace=True)


def safe_eval(val):
    if isinstance(val, str):
        try:
            return ast.literal_eval(val)
        except:
            return []
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