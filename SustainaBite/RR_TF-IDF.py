import pandas as pd
import os
import xgboost as xgb
from sklearn.feature_extraction.text import TfidfVectorizer
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

# 1. Convert the list of ingredients into a single string per recipe
# Example: ['eggs', 'salt', 'pepper'] -> "eggs salt pepper"
final_data['ingredients'] = final_data['ingredients'].apply(lambda x: ' '.join(eval(x)))
# Note: eval() is needed if your Excel loaded the list as a literal string "['a', 'b']"

print(f"Colums found: {list(final_data.columns)}")

# 2. Initialize TF-IDF
tfidf = TfidfVectorizer(
    max_features=500,  # Keep only top 500 most important ingredients to save memory
    stop_words='english' # Removes 'the', 'and', etc.
)

# 3. Fit and Transform
ingredient_features = tfidf.fit_transform(final_data['ingredients'])

# 4. Convert to DataFrame (so you can join it later)
ingredients_df = pd.DataFrame(
    ingredient_features.toarray(),
    columns=tfidf.get_feature_names_out()
)

#finilsed dataframe read for ML
normalised_data = final_data.join(ingredients_df)

# ---------------------------------------------------------
# 1. PREPARE X (Inputs) AND y (Output)
# ---------------------------------------------------------

# Define the target variable
target_col = 'average_rating'

# Define the columns you DO NOT want in your training inputs.
# You need to remove ID, Name, dates, and the target itself.
# Adjust this list based on what metadata you kept in 'normalised_data'
cols_to_drop = [
    'id',
    'name',
    'minutes',
    'contributor_id',
    'submitted',
    'tags',
    'nutrition',
    'n_steps',
    'steps',
    'description',
    'ingredients',          # The raw list string
    'n_ingredients',
    'ingredients_string',   # The string you made for TF-IDF
    'average_rating',       # The target! Important to drop.
    'rating_count'          # Bias risk (popular recipes != tasty recipes)
]

# Create X and y
# errors='ignore' ensures it doesn't crash if one of the drop_cols is missing
X = normalised_data.drop(columns=cols_to_drop, errors='ignore')
y = normalised_data[target_col]

print(f"Input Shape: {X.shape}") # Should be (Rows, ~500 features)
print(f"Target Shape: {y.shape}")

# ---------------------------------------------------------
# 2. SPLIT DATA (Train / Validate / Test)
# ---------------------------------------------------------
# We want: 70% Train, 15% Validation, 15% Test

# First, split into Train (70%) and Temp (30%)
X_train, X_temp, y_train, y_temp = train_test_split(
    X, y, test_size=0.3, random_state=42
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
model = xgb.XGBRegressor(
    objective='reg:squarederror', # Standard for regression
    n_estimators=1000,            # Max number of trees
    learning_rate=0.05,           # Slower learning prevents overfitting
    max_depth=6,                  # Depth of tree
    early_stopping_rounds=50,     # Stop if validation score stops improving
    n_jobs=-1,                    # Use all CPU cores
    random_state=42
)

# Fit the model
# We pass the Validation set here so the model can check its progress
print("Starting training...")
model.fit(
    X_train, y_train,
    eval_set=[(X_train, y_train), (X_val, y_val)],
    verbose=100  # Print progress every 100 trees
)

# ---------------------------------------------------------
# 4. EVALUATE ON TEST SET (The "Final Exam")
# ---------------------------------------------------------

# Predict on the hold-out Test set
predictions = model.predict(X_test)

# Calculate error metrics
mae = mean_absolute_error(y_test, predictions)
mse = mean_squared_error(y_test, predictions)

print("------------------------------------------------")
print(f"Mean Absolute Error (MAE): {mae:.4f}")
print("------------------------------------------------")

# What this means:
# If MAE is 0.5, your model is, on average, off by half a star.