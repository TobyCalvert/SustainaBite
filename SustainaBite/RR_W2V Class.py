import pandas as pd
import os
import xgboost as xgb
import numpy as np
from gensim.models import Word2Vec
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, roc_auc_score

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

    # Save it as a pickle for next time
    print("Saving to cache...")
    data_recipes.to_pickle(cache_file_recipes)

if os.path.exists(cache_file_interactions):
    print("Loading from fast cache...")
    data_interactions = pd.read_pickle(cache_file_interactions)
else:
    print("Reading slow interactions Excel file (this happens only once)...")
    data_interactions = pd.read_excel(raw_file_interactions)

    # Save it as a pickle for next time
    print("Saving to cache...")
    data_interactions.to_pickle(cache_file_interactions)

print("Data loaded!")

data_interactions.drop(data_interactions[data_interactions['rating']==0].index, inplace=True)

# 1. Group the interactions by recipe_id to get one row per recipe
aggregated_ratings = data_interactions.groupby('recipe_id').agg({
    'rating': ['mean', 'count'] # Get average and number of ratings
}).reset_index()

# 2. Flatten the confusing column names created by aggregation
aggregated_ratings.columns = ['id', 'average_rating', 'rating_count']

# 3. NOW merge this clean summary back to your recipes
final_data = pd.merge(
    data_recipes,
    aggregated_ratings,
    on='id',
    how='left' # Keep all recipes, even those with no ratings yet
)

# 4. Fill NaN values (recipes with 0 reviews)
final_data['average_rating'] = final_data['average_rating'].fillna(0)
final_data['rating_count'] = final_data['rating_count'].fillna(0)

# ---------------------------------------------------------
# 1. PREPARE DATA FOR WORD2VEC
# ---------------------------------------------------------
# Word2Vec needs a list of lists: [['egg', 'salt'], ['tomato', 'basil']]
# Assuming final_data['ingredients'] is currently a string representation like "['egg', 'salt']"
# We use eval() to convert it back to a real Python list.
print("Parsing ingredient lists...")
recipes_ingredients = final_data['ingredients'].apply(eval).tolist()

# ---------------------------------------------------------
# 2. TRAIN THE WORD2VEC MODEL
# ---------------------------------------------------------
print("Training Word2Vec model on your ingredients...")
# vector_size=100: Compresses every ingredient into a vector of 100 numbers
# window=5: Looks at ingredients 5 spots away to learn context
# min_count=5: Ignores ingredients that appear in fewer than 5 recipes
w2v_model = Word2Vec(
    sentences=recipes_ingredients,
    vector_size=100,
    window=5,
    min_count=5,
    workers=4,
    seed=42
)


# Optional: Check if it learned relationships
# print(w2v_model.wv.most_similar('chicken'))
# Should output things like 'turkey', 'pork', etc.

# ---------------------------------------------------------
# 3. VECTORIZE RECIPES (The Averaging Step)
# ---------------------------------------------------------
# A recipe is just the AVERAGE of all its ingredient vectors.
# Recipe_Vector = (Vector(Egg) + Vector(Salt)) / 2

def get_recipe_vector(ingredient_list, model):
    # Filter out ingredients that didn't make the cut (min_count=5)
    valid_vectors = [model.wv[word] for word in ingredient_list if word in model.wv]

    if len(valid_vectors) == 0:
        # If a recipe has no valid ingredients, return a row of zeros
        return np.zeros(model.vector_size)

    # Calculate the mean (average) vector
    return np.mean(valid_vectors, axis=0)


print("Vectorizing all recipes...")
# Create a list of 100-dimensional vectors
recipe_vectors = [get_recipe_vector(recipe, w2v_model) for recipe in recipes_ingredients]

# Convert to DataFrame
# This replaces your old 'ingredients_df' / TF-IDF matrix
X_embeddings = pd.DataFrame(recipe_vectors)
X_embeddings.columns = [f'vec_{i}' for i in range(100)]  # Rename cols to vec_0, vec_1...

# ---------------------------------------------------------
# 4. PREPARE FINAL INPUTS (X)
# ---------------------------------------------------------
# Join the new vectors with any other metadata you want (like prep time)
# Note: We reset indices to ensure they align perfectly
final_data.reset_index(drop=True, inplace=True)
X_embeddings.reset_index(drop=True, inplace=True)

# 1. Parse the 'nutrition' column (it's a string looking like a list)
# Format is usually [calories, total_fat, sugar, sodium, protein, saturated_fat, carbs]
nutrition_df = final_data['nutrition'].str.strip('[]').str.split(', ', expand=True)
nutrition_df.columns = ['calories', 'total_fat', 'sugar', 'sodium', 'protein', 'sat_fat', 'carbs']

# 2. Convert to float
nutrition_df = nutrition_df.astype(float)

# 3. Add 'minutes' and 'n_steps'
metadata_df = final_data[['minutes', 'n_steps']].copy()

# 4. Join everything to your existing Embeddings
# X_embeddings is your 100-column Word2Vec dataframe
X_final = pd.concat([X_embeddings, metadata_df, nutrition_df], axis=1)

print(f"New Feature Count: {X_final.shape[1]}")
# Now you have Ingredients + Time + Complexity + Fat + Sugar

# Combine (if you have other numerical cols in final_data you want to keep)
# For now, let's just use the embeddings as our ingredients input
X = X_final

# Add back other metadata if you have it (Example)
# X['minutes'] = final_data['minutes']
# X['n_steps'] = final_data['n_steps']

y_class = (final_data['average_rating'] >= 3.0).astype(int)

print(f"New Input Shape: {X.shape}")
# Shape should be (Num_Recipes, 100)

# ---------------------------------------------------------
# 2. SPLIT DATA (Train / Validate / Test)
# ---------------------------------------------------------
# We want: 70% Train, 15% Validation, 15% Test

# First, split into Train (70%) and Temp (30%)
X_train, X_temp, y_train, y_temp = train_test_split(
    X, y_class, test_size=0.3, random_state=42
)

# Next, split Temp into Validation (50% of temp) and Test (50% of temp)
X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.5, random_state=42
)

print(f"Training sets: {X_train.shape}")
print(f"Validation sets: {X_val.shape}")
print(f"Test sets: {X_test.shape}")

# ---------------------------------------------------------
# 3. CONFIGURE & TRAIN XGBOOST
# ---------------------------------------------------------

# Initialize the Regressor
model = xgb.XGBClassifier(
    objective='binary:logistic',
    eval_metric='auc',
    n_estimators=1000,            # Max number of trees
    learning_rate=0.05,           # Slower learning prevents overfitting
    max_depth=6,                  # Depth of tree
    early_stopping_rounds=50,     # Stop if validation score stops improving
    random_state=42,

    device="cuda",
    tree_method="hist"
)

# Fit the model
# We pass the Validation set here so the model can check its progress
print("Starting training...")

# Create a weight column based on the number of ratings
# We use log() because 1000 reviews isn't 1000x more important than 1 review, maybe just 3x
import numpy as np
weights = np.log1p(final_data['rating_count'])

model.fit(
    X_train, y_train,
    sample_weight=weights.iloc[X_train.index], # Align weights to training rows
    eval_set=[(X_train, y_train), (X_val, y_val)],
    verbose=100  # Print progress every 100 trees
)

# ---------------------------------------------------------
# 4. EVALUATE ON TEST SET (The "Final Exam")
# ---------------------------------------------------------

# Predict on the hold-out Test set
hard_predictions = model.predict(X_test)
probs = model.predict_proba(X_test)[:, 1]

# Calculate error metrics
mae = mean_absolute_error(y_test, hard_predictions)
mse = mean_squared_error(y_test, hard_predictions)
auc_score = roc_auc_score(y_test, probs)

print("------------------------------------------------")
print(f"Mean Absolute Error (MAE): {mae:.4f}")
print(f"Mean Squared Error (MSE): {mse:.4f}")
print(f"Area Under Curve (AUC): {auc_score:.4f}")
print("------------------------------------------------")