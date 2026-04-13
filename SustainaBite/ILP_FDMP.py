import pulp as lp
import json
import os

# --- 1. CONFIGURATION ---
DB_FILE = "json files/food_database_complete.json"


def analyze_database(food_db):
    """
    Checks if the database has enough variety to actually solve the problem.
    Returns False if critical categories are missing.
    """
    categories = {"Fruit": 0, "Grain": 0, "Meat": 0, "Vegetable": 0, "Fish": 0, "Sweet": 0}

    print(f"\n--- Database Diagnostics ({len(food_db)} items total) ---")

    for name, data in food_db.items():
        cat = data.get("category", "Unknown")
        if cat in categories:
            categories[cat] += 1

    # Print counts
    for cat, count in categories.items():
        status = "OK" if count > 0 else "CRITICAL ERROR (0 found)"
        print(f"  {cat.ljust(10)}: {count} items \t[{status}]")

    print("-" * 40)

    # Check for deal-breakers
    if categories["Grain"] == 0:
        print("❌ STOPPING: No 'Grain' items found. Breakfast/Dinner constraints cannot be met.")
        print("   -> Check climatiq_mapping.json to ensure bread/rice/pasta IDs are correct.")
        print("   -> Check build_food_database.py log to see if they were skipped due to 0 CO2e.")
        return False

    if categories["Meat"] == 0:
        print("❌ STOPPING: No 'Protein' items found. Lunch/Dinner constraints cannot be met.")
        return False

    if categories["Fruit"] == 0:
        print("❌ STOPPING: No 'Fruit' items found. Breakfast constraints cannot be met.")
        return False

    return True


def generate_meal_plan():
    print("--- Loading Database ---")
    if not os.path.exists(DB_FILE):
        print(f"Error: {DB_FILE} not found. Please run 'build_food_database.py' first.")
        return

    with open(DB_FILE, "r") as f:
        raw_db = json.load(f)

    # --- FILTER INVALID DATA ---
    # Automatically exclude items where CO2e is 0 (indicates API error or missing data)
    FOOD_DB = {name: data for name, data in raw_db.items() if data.get('co2_per_kg', 0) > 0}

    dropped_count = len(raw_db) - len(FOOD_DB)
    if dropped_count > 0:
        print(f"Warning: Removed {dropped_count} items with 0.00 CO2e from calculations.")

    # RUN DIAGNOSTICS
    if not analyze_database(FOOD_DB):
        return

    MEALS = ["Breakfast", "Lunch", "Dinner"]

    # --- 2. DEFINE THE PROBLEM ---
    prob = lp.LpProblem("Daily_Meal_Plan_Optimizer", lp.LpMinimize)

    # --- 3. CREATE VARIABLES ---
    food_vars = {}
    for meal in MEALS:
        for food_name in FOOD_DB:
            var_name = f"{meal}_{food_name}"
            food_vars[var_name] = lp.LpVariable(var_name, lowBound=0, upBound=2, cat='Integer')

    # --- 4. OBJECTIVE FUNCTION ---
    total_co2 = 0
    for meal in MEALS:
        for food_name, data in FOOD_DB.items():
            var = food_vars[f"{meal}_{food_name}"]
            item_co2 = var * data['serving_kg'] * data['co2_per_kg']
            total_co2 += item_co2

    prob += total_co2, "Total_Daily_CO2e"

    # --- 5. CONSTRAINTS ---

    # Calculate variables for use in constraints
    total_calories = 0
    for meal in MEALS:
        for food_name, data in FOOD_DB.items():
            var = food_vars[f"{meal}_{food_name}"]
            total_calories += var * data['serving_kg'] * data['kcal_per_kg']

    # Widened Global Range slightly (1600 - 2400) to allow easier solving
    prob += total_calories >= 1600, "Min_Daily_Cals"
    prob += total_calories <= 2400, "Max_Daily_Cals"

    # --- BREAKFAST ---
    # Widened Range: 250 - 700 kcal
    b_cals = lp.lpSum([food_vars[f"Breakfast_{f}"] * d['serving_kg'] * d['kcal_per_kg'] for f, d in FOOD_DB.items()])
    prob += b_cals >= 250
    prob += b_cals <= 700

    # Must have at least 1 Fruit OR 1 Grain (Relaxed from AND to OR if needed, keeping AND for now)
    prob += lp.lpSum([food_vars[f"Breakfast_{f}"] for f, d in FOOD_DB.items() if d['category'] == "Fruit"]) >= 1
    prob += lp.lpSum([food_vars[f"Breakfast_{f}"] for f, d in FOOD_DB.items() if d['category'] == "Grain"]) >= 1

    # --- LUNCH ---
    # Widened Range: 400 - 900 kcal
    l_cals = lp.lpSum([food_vars[f"Lunch_{f}"] * d['serving_kg'] * d['kcal_per_kg'] for f, d in FOOD_DB.items()])
    prob += l_cals >= 400
    prob += l_cals <= 900

    prob += lp.lpSum([food_vars[f"Lunch_{f}"] for f, d in FOOD_DB.items() if d['category'] == "Meat"]) >= 1
    prob += lp.lpSum([food_vars[f"Lunch_{f}"] for f, d in FOOD_DB.items() if d['category'] == "Vegetable"]) >= 1

    # --- DINNER ---
    # Widened Range: 500 - 1000 kcal
    d_cals = lp.lpSum([food_vars[f"Dinner_{f}"] * d['serving_kg'] * d['kcal_per_kg'] for f, d in FOOD_DB.items()])
    prob += d_cals >= 500
    prob += d_cals <= 1000

    prob += lp.lpSum([food_vars[f"Dinner_{f}"] for f, d in FOOD_DB.items() if d['category'] in ["Meat", "Fish"]]) >= 1
    prob += lp.lpSum([food_vars[f"Dinner_{f}"] for f, d in FOOD_DB.items() if d['category'] == "Grain"]) >= 1

    # --- 6. SOLVE ---
    print("Optimizing meal plan (may take a moment)...")
    prob.solve(lp.PULP_CBC_CMD(msg=False))


    # --- 7. DISPLAY & SAVE RESULTS ---
    print(f"\nStatus: {lp.LpStatus[prob.status]}")

    if lp.LpStatus[prob.status] == 'Optimal':
        print(f"Total Daily CO2e: {lp.value(prob.objective):.4f} kg")

        # ### NEW: Initialize dictionary to store the plan
        daily_plan_export = {}

        for meal in MEALS:
            print(f"\n[{meal.upper()}]")

            # ### NEW: List to hold ingredients for this meal
            current_meal_ingredients = []

            for food_name, data in FOOD_DB.items():
                # Construct variable name matching how you created it
                var_name = f"{meal}_{food_name}"
                var = food_vars[var_name]
                servings = lp.value(var)

                # Check if it was selected (handling floating point tolerance)
                if servings and servings > 0.1:
                    # ### NEW: Add to our export list
                    # We just want the name, e.g., "oats"
                    current_meal_ingredients.append(food_name)

                    # (Your existing print logic...)
                    weight = servings * data['serving_kg']
                    cals = weight * data['kcal_per_kg']
                    co2 = weight * data['co2_per_kg']
                    print(f"  - {food_name.ljust(35)} | {servings:.1f} srv")

            # ### NEW: Save this meal's list to the master dictionary
            daily_plan_export[meal] = current_meal_ingredients

        # ### NEW: Write to file
        output_filename = "json files/ilp_output.json"
        with open(output_filename, "w") as f:
            json.dump(daily_plan_export, f, indent=4)

        print(f"\n✅ Success! Plan saved to {output_filename}")

    else:
        print("Optimization Failed.")


if __name__ == "__main__":
    generate_meal_plan()