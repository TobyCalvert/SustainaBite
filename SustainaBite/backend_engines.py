import pandas as pd
import json
import ast
import os
import gensim
from functools import lru_cache
from datetime import datetime, date

# --- 1. CONFIGURATION ---
INGREDIENTS_JSON = "json files/food_database_complete.json"
RECIPES_PKL = "Data/archive/recipes_optimized.pkl"
OUTPUT_WEEKLY_FILE = "json files/weekly_plan.json"

# --- Load Word2Vec globally in the backend ---
try:
    w2v_model = gensim.models.Word2Vec.load("Data/archive/ingredient_w2v.model")
except:
    w2v_model = None

# --- 2. TEXT PROCESSING  ---
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

def check_tags(cell_data, required_tags):
    if isinstance(cell_data, str):
        try: actual_list = ast.literal_eval(cell_data)
        except: actual_list = [cell_data]
    elif isinstance(cell_data, (list, tuple)):
        actual_list = cell_data
    else: return False
    clean_tags = [str(t).strip().lower() for t in actual_list]
    return all(req.lower() in clean_tags for req in required_tags)


def contains_excluded_tags(cell_data, excluded_tags):
    if not excluded_tags:
        return False

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
    # Return True if ANY excluded tag is found in the recipe's clean tags
    return any(ex.lower() in clean_tags for ex in excluded_tags)

# --- 3. GLOBAL DATABASE LOADING ---
try:
    with open(INGREDIENTS_JSON, "r") as f:
        raw_db = json.load(f)
    db_standardized = {standardize_ingredient(k): v for k, v in raw_db.items()}
except FileNotFoundError:
    db_standardized = {}

# --- 4. THE MASS ESTIMATOR ---
def estimate_serving_kg(item_name):
    """
    Estimates the weight of 1 serving of food using a 3-step heuristic cascade.
    """
    clean_name = item_name.lower().strip()

    # 1. Direct Database Match
    if clean_name in db_standardized and 'serving_kg' in db_standardized[clean_name]:
        return float(db_standardized[clean_name]['serving_kg'])

    # 2. AI Word2Vec Imputation (Borrow weight from closest known neighbor)
    if w2v_model and clean_name in w2v_model.wv:
        similars = w2v_model.wv.most_similar(clean_name, topn=15)
        for sim_word, similarity_score in similars:
            if sim_word in db_standardized and 'serving_kg' in db_standardized[sim_word]:
                return float(db_standardized[sim_word]['serving_kg'])

    # 3. Global Fallback (150 grams)
    return 0.15

# --- 5. THE OPTIMIZATION ENGINE ---
def generate_meal_plan(pantry_data, min_match_threshold=0.70, user_tags=None, excluded_tags=None, min_ingredients=6.0, days=7,
                       min_rating=0.0, auto_swap=False):
    print("--- 1. Initializing Weekly Optimization Engine ---")

    if user_tags is None:
        user_tags = []

    today = date.today()

    current_pantry = {}
    for item in pantry_data:
        std_name = standardize_ingredient(item.get("name", ""))
        is_inf = item.get("is_infinite", False)

        # --- If staple, ignore the date check entirely ---
        if is_inf:
            current_pantry[std_name] = {
                "exp_date": None,
                "quantity": "∞",
                "is_infinite": True
            }
        else:
            try:
                exp_date = datetime.strptime(item.get("date", ""), "%Y-%m-%d").date()
                if exp_date >= today:
                    current_pantry[std_name] = {
                        "exp_date": exp_date,
                        "quantity": item.get("quantity", 1),
                        "is_infinite": False
                    }
            except:
                pass

    df_all = pd.read_pickle(RECIPES_PKL)

    # 1. Filter by Rating
    df_all['rating'] = pd.to_numeric(df_all['rating'], errors='coerce').fillna(0.0)
    if min_rating > 0:
        df_all = df_all[df_all['rating'] >= min_rating]

    # 2. Filter out Excluded Tags
    if excluded_tags:
        # The '~' symbol means "NOT". So we keep recipes that DO NOT contain excluded tags.
        df_all = df_all[~df_all['tags'].apply(lambda c: contains_excluded_tags(c, excluded_tags))]

    # 3. Reset index to fix memory fragmentation
    df_all = df_all.reset_index(drop=True)

    breakfast_tags = ["breakfast"] + user_tags
    lunch_tags = ["lunch"] + user_tags
    dinner_tags = ["main-dish"] + user_tags

    # --- Convert directly to pure Python dictionaries ---
    df_pools = {
        "Breakfast": df_all[df_all['tags'].apply(lambda c: check_tags(c, breakfast_tags))].to_dict('records'),
        "Lunch": df_all[df_all['tags'].apply(lambda c: check_tags(c, lunch_tags))].to_dict('records'),
        "Dinner": df_all[df_all['tags'].apply(lambda c: check_tags(c, dinner_tags))].to_dict('records')
    }

    used_recipes = set()
    weekly_plan = []
    w2v_swap_cache = {}

    print("--- 2. Generating Plan (Optimizing for Food Waste & Depletion) ---")

    for day in range(days):
        day_plan = {}

        for meal_type, df_pool in df_pools.items():
            best_recipe = None
            best_effective_score = float('inf')

            # --- Iterate through dicts using enumerate() ---
            for index, row in enumerate(df_pool):
                recipe_name = row.get('name', f"Recipe_{index}")
                if recipe_name in used_recipes:
                    continue

                raw_ingredients = row.get('ingredients', [])
                if isinstance(raw_ingredients, str):
                    try:
                        raw_ingredients = ast.literal_eval(raw_ingredients)
                    except:
                        raw_ingredients = []
                elif not isinstance(raw_ingredients, list):
                    raw_ingredients = []

                clean_raw_ingredients = [ing for ing in raw_ingredients if str(ing).strip()]

                if len(clean_raw_ingredients) <= min_ingredients:
                    continue

                matched_count, total_co2, effective_score = 0, 0, 0
                matched_details, unmatched_details, pantry_items_used = [], [], []

                for orig_ing in clean_raw_ingredients:
                    std_ing = standardize_ingredient(str(orig_ing))

                    # --- Auto-Swap Interceptor ---
                    swapped_pantry_item = None
                    if auto_swap and w2v_model and (std_ing not in current_pantry) and (std_ing in w2v_model.wv):

                        # Check if ALREADY asked about this ingredient
                        if std_ing not in w2v_swap_cache:
                            # If not, save the answer to the dictionary
                            w2v_swap_cache[std_ing] = w2v_model.wv.most_similar(std_ing, topn=15)

                        for sim, _ in w2v_swap_cache[std_ing]:
                            if sim in current_pantry:
                                swapped_pantry_item = sim
                                break

                    # Point the engine to the swapped item (or keep it as the original if no swap happened)
                    actual_pantry_item = swapped_pantry_item if swapped_pantry_item else std_ing

                    # --- Score based on the actual_pantry_item ---
                    if actual_pantry_item in current_pantry:
                        if current_pantry[actual_pantry_item]["is_infinite"]:
                            effective_score -= 1.0
                            base_tag = "♾️ STAPLE"
                        else:
                            # It's finite, check the expiration date
                            days_left = (current_pantry[actual_pantry_item]["exp_date"] - today).days
                            if days_left <= 3:
                                effective_score -= 15.0
                                base_tag = "🚨 EXPIRING SOON"
                            elif days_left <= 7:
                                effective_score -= 5.0
                                base_tag = "🟠 PANTRY"
                            else:
                                effective_score -= 1.0
                                base_tag = "🟢 PANTRY"

                        # Create a special tag if it was swapped
                        if swapped_pantry_item:
                            tag = f"🔄 SWAP: {swapped_pantry_item.title()} ({base_tag})"
                        else:
                            tag = base_tag

                        matched_count += 1
                        pantry_items_used.append(actual_pantry_item)
                        matched_details.append(f"{orig_ing} -> [{tag}: 0 CO2]")

                    elif std_ing in db_standardized:
                        db_data = db_standardized[std_ing]
                        weight = db_data.get('serving_kg', 0)
                        co2_val = db_data.get('co2_per_kg', 0)

                        total_co2 += weight * co2_val
                        effective_score += weight * co2_val
                        matched_count += 1
                        matched_details.append(f"{orig_ing} -> {db_data.get('clean_name', std_ing)}")
                    else:
                        unmatched_details.append(orig_ing)

                if (matched_count / max(1, len(clean_raw_ingredients))) >= min_match_threshold:
                    if effective_score < best_effective_score:
                        best_effective_score = effective_score

                        raw_nut = row.get('nutrition', [])
                        if isinstance(raw_nut, str):
                            try:
                                raw_nut = ast.literal_eval(raw_nut)
                            except:
                                raw_nut = []
                        elif not isinstance(raw_nut, (list, tuple)):
                            raw_nut = []

                        nutrition_dict = {
                            "calories": raw_nut[0] if len(raw_nut) > 0 else 0,
                            "total_fat": raw_nut[1] if len(raw_nut) > 1 else 0,
                            "sugar": raw_nut[2] if len(raw_nut) > 2 else 0,
                            "sodium": raw_nut[3] if len(raw_nut) > 3 else 0,
                            "protein": raw_nut[4] if len(raw_nut) > 4 else 0,
                            "saturated_fat": raw_nut[5] if len(raw_nut) > 5 else 0,
                            "carbs": raw_nut[6] if len(raw_nut) > 6 else 0,
                        }

                        instructions = row.get('steps', [])
                        if isinstance(instructions, str):
                            try:
                                instructions = ast.literal_eval(instructions)
                            except:
                                instructions = []
                        elif not isinstance(instructions, list):
                            instructions = []

                        best_recipe = {
                            "title": recipe_name,
                            "rating": row.get('rating', 0.0),
                            "is_predicted": row.get('is_predicted_rating', False),
                            "total_co2": round(total_co2, 4),
                            "nutrition": nutrition_dict,
                            "instructions": instructions,
                            "match_ratio": round(matched_count / len(clean_raw_ingredients), 3),
                            "matched_items": matched_details,
                            "unmatched_items": unmatched_details,
                            "_consumed_pantry_items": pantry_items_used
                        }

            if best_recipe:
                used_recipes.add(best_recipe["title"])
                for item in best_recipe["_consumed_pantry_items"]:
                    if item in current_pantry:
                        # Only subtract if the user didn't check the "Infinite" box
                        if not current_pantry[item]["is_infinite"]:
                            current_pantry[item]["quantity"] -= 1
                            if current_pantry[item]["quantity"] <= 0:
                                del current_pantry[item]
                day_plan[meal_type] = best_recipe
            else:
                day_plan[meal_type] = None

        weekly_plan.append(day_plan)

    os.makedirs(os.path.dirname(OUTPUT_WEEKLY_FILE), exist_ok=True)
    with open(OUTPUT_WEEKLY_FILE, "w") as f:
        json.dump(weekly_plan, f, indent=4)

    print("✅ Weekly plan generated successfully.")
    return weekly_plan


def generate_single_recipe_options(pantry_data, target_tag, min_match_threshold=0.70, user_tags=None, excluded_tags=None, min_ingredients=6,
                                   top_n=5, min_rating=0.0, auto_swap=False):
    if user_tags is None: user_tags = []

    today = date.today()

    current_pantry = {}
    for item in pantry_data:
        std_name = standardize_ingredient(item.get("name", ""))
        is_inf = item.get("is_infinite", False)

        # --- If infinite, ignore the date check entirely ---
        if is_inf:
            current_pantry[std_name] = {
                "exp_date": None,
                "quantity": "∞",
                "is_infinite": True
            }
        else:
            try:
                exp_date = datetime.strptime(item.get("date", ""), "%Y-%m-%d").date()
                if exp_date >= today:
                    current_pantry[std_name] = {
                        "exp_date": exp_date,
                        "quantity": item.get("quantity", 1),
                        "is_infinite": False
                    }
            except:
                pass

    df_all = pd.read_pickle(RECIPES_PKL)

    # 1. Filter by Rating
    df_all['rating'] = pd.to_numeric(df_all['rating'], errors='coerce').fillna(0.0)
    if min_rating > 0:
        df_all = df_all[df_all['rating'] >= min_rating]

    # ---  Filter out Excluded Tags ---
    if excluded_tags:
        # The '~' symbol means "NOT". So we keep recipes that DO NOT contain excluded tags.
        df_all = df_all[~df_all['tags'].apply(lambda c: contains_excluded_tags(c, excluded_tags))]

    #  Reset index to fix memory fragmentation
    df_all = df_all.reset_index(drop=True)

    # --- SAFETY NET: Prevent 'NoneType' crash ---
    if user_tags is None:
        user_tags = []

    combined_tags = [target_tag] + user_tags

    # --- Convert to Dictionaries ---
    df_pool = df_all[df_all['tags'].apply(lambda c: check_tags(c, combined_tags))].to_dict('records')

    scored_recipes = []

    w2v_swap_cache = {}

    # --- Enumerate ---
    for index, row in enumerate(df_pool):
        raw_ingredients = row.get('ingredients', [])
        if isinstance(raw_ingredients, str):
            try:
                raw_ingredients = ast.literal_eval(raw_ingredients)
            except:
                raw_ingredients = []
        elif not isinstance(raw_ingredients, list):
            raw_ingredients = []

        clean_raw_ingredients = [ing for ing in raw_ingredients if str(ing).strip()]

        if len(clean_raw_ingredients) < min_ingredients: continue

        matched_count, total_co2, effective_score = 0, 0, 0
        matched_details, unmatched_details, pantry_items_used = [], [], []

        for orig_ing in clean_raw_ingredients:
            std_ing = standardize_ingredient(str(orig_ing))

            # --- Auto-Swap Interceptor ---
            swapped_pantry_item = None
            if auto_swap and w2v_model and (std_ing not in current_pantry) and (std_ing in w2v_model.wv):

                # Check if ALREADY asked about this ingredient
                if std_ing not in w2v_swap_cache:
                    # If not, save the answer to the dictionary
                    w2v_swap_cache[std_ing] = w2v_model.wv.most_similar(std_ing, topn=15)

                for sim, _ in w2v_swap_cache[std_ing]:
                    if sim in current_pantry:
                        swapped_pantry_item = sim
                        break

            # Point the engine to the swapped item (or keep it as the original if no swap happened)
            actual_pantry_item = swapped_pantry_item if swapped_pantry_item else std_ing

            # --- Score based on the actual_pantry_item ---
            if actual_pantry_item in current_pantry:
                if current_pantry[actual_pantry_item]["is_infinite"]:
                    effective_score -= 1.0
                    base_tag = "♾️ STAPLE"
                else:
                    # It's finite, check the expiration date
                    days_left = (current_pantry[actual_pantry_item]["exp_date"] - today).days
                    if days_left <= 3:
                        effective_score -= 15.0
                        base_tag = "🚨 EXPIRING SOON"
                    elif days_left <= 7:
                        effective_score -= 5.0
                        base_tag = "🟠 PANTRY"
                    else:
                        effective_score -= 1.0
                        base_tag = "🟢 PANTRY"

                # Create a special tag if it was swapped
                if swapped_pantry_item:
                    tag = f"🔄 SWAP: {swapped_pantry_item.title()} ({base_tag})"
                else:
                    tag = base_tag

                matched_count += 1
                pantry_items_used.append(actual_pantry_item)
                matched_details.append(f"{orig_ing} -> [{tag}: 0 CO2]")

            elif std_ing in db_standardized:
                db_data = db_standardized[std_ing]
                weight, co2_val = db_data.get('serving_kg', 0), db_data.get('co2_per_kg', 0)
                total_co2 += weight * co2_val
                effective_score += weight * co2_val
                matched_count += 1
                matched_details.append(f"{orig_ing} -> {db_data.get('clean_name', std_ing)}")
            else:
                unmatched_details.append(orig_ing)

        if len(clean_raw_ingredients) > 0 and (matched_count / len(clean_raw_ingredients)) >= min_match_threshold:
            raw_nut = row.get('nutrition', [])
            if isinstance(raw_nut, str):
                try:
                    raw_nut = ast.literal_eval(raw_nut)
                except:
                    raw_nut = []
            elif not isinstance(raw_nut, (list, tuple)):
                raw_nut = []

            nutrition_dict = {
                "calories": raw_nut[0] if len(raw_nut) > 0 else 0,
                "total_fat": raw_nut[1] if len(raw_nut) > 1 else 0,
                "sugar": raw_nut[2] if len(raw_nut) > 2 else 0,
                "sodium": raw_nut[3] if len(raw_nut) > 3 else 0,
                "protein": raw_nut[4] if len(raw_nut) > 4 else 0,
                "saturated_fat": raw_nut[5] if len(raw_nut) > 5 else 0,
                "carbs": raw_nut[6] if len(raw_nut) > 6 else 0,
            }

            instructions = row.get('steps', [])
            if isinstance(instructions, str):
                try:
                    instructions = ast.literal_eval(instructions)
                except:
                    instructions = []
            elif not isinstance(instructions, list):
                instructions = []

            scored_recipes.append({
                "title": row.get('name', f"Recipe_{index}"),
                "rating": row.get('rating', 0.0),
                "is_predicted": row.get('is_predicted_rating', False),
                "total_co2": round(total_co2, 4),
                "nutrition": nutrition_dict,
                "instructions": instructions,
                "effective_score": effective_score,
                "match_ratio": round(matched_count / len(clean_raw_ingredients), 3),
                "matched_items": matched_details,
                "unmatched_items": unmatched_details,
            })

    scored_recipes.sort(key=lambda x: x['effective_score'])
    return scored_recipes[:top_n]