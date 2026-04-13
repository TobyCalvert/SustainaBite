import json
import os

# --- 1. CONFIGURATION ---
UNMATCHED_CARBON_FILE = "json files/unmatched_carbon_report.json"
UNMATCHED_RECIPES_FILE = "json files/unmatched_recipes_report.json"

SECONDARY_MATCHES_FILE = "json files/secondary_loose_matches.json"
FINAL_UNMATCHED_RECIPES = "final_unmatched_recipes.json"


def run_loose_matching_pass():
    print("--- 1. Loading Pass 1 Leftovers ---")

    if not os.path.exists(UNMATCHED_CARBON_FILE) or not os.path.exists(UNMATCHED_RECIPES_FILE):
        print("❌ Error: Missing Pass 1 report files. Run the exact match script first.")
        return

    with open(UNMATCHED_CARBON_FILE, "r") as f:
        carbon_data = json.load(f)
        # Format is { "original_db_key": "standardized_name" }
        unmatched_db_items = carbon_data.get("Unmatched_Items", {})

    with open(UNMATCHED_RECIPES_FILE, "r") as f:
        recipe_data = json.load(f)
        # Format is { "original_recipe_string": "standardized_name" }
        unmatched_recipe_items = recipe_data.get("Unmatched_Items", {})

    print(f"Loaded {len(unmatched_recipe_items)} orphaned recipe ingredients.")
    print(f"Loaded {len(unmatched_db_items)} orphaned carbon DB items.")
    print("\n--- 2. Running Loose Match Logic ---")

    secondary_matches = {}
    still_unmatched_recipes = {}

    # Keep track of DB items we use so we don't assign them to a dozen different things unnecessarily
    # (Though in loose matching, one DB item like "oil" might legitimately match "olive oil" and "sesame oil")
    used_db_keys = set()

    for orig_rec_str, std_rec_str in unmatched_recipe_items.items():
        match_found = False

        # We skip completely empty strings that might have been stripped to nothing
        if not std_rec_str.strip():
            still_unmatched_recipes[orig_rec_str] = std_rec_str
            continue

        for orig_db_key, std_db_str in unmatched_db_items.items():
            if not std_db_str.strip() or len(std_db_str) < 3:
                continue  # Skip tiny words to prevent 'ox' matching inside 'box'

            # LOOSE RULE 1: Substring Match (DB is inside Recipe)
            # e.g., DB = "wine", Recipe = "red wine"
            if std_db_str in std_rec_str:
                secondary_matches[
                    orig_rec_str] = f"Loose Match -> '{orig_db_key}' (Because '{std_db_str}' is in '{std_rec_str}')"
                used_db_keys.add(orig_db_key)
                match_found = True
                break

            # LOOSE RULE 2: Substring Match (Recipe is inside DB)
            # e.g., Recipe = "vinegar", DB = "red wine vinegar"
            elif std_rec_str in std_db_str:
                secondary_matches[
                    orig_rec_str] = f"Loose Match -> '{orig_db_key}' (Because '{std_rec_str}' is in '{std_db_str}')"
                used_db_keys.add(orig_db_key)
                match_found = True
                break

        if not match_found:
            still_unmatched_recipes[orig_rec_str] = std_rec_str

    # --- 3. EXPORT RESULTS ---
    print("\n--- 3. Saving Secondary Pass Files ---")

    # Save the new matches
    with open(SECONDARY_MATCHES_FILE, "w") as f:
        sorted_matches = dict(sorted(secondary_matches.items()))
        json.dump({
            "Total_Secondary_Matches": len(sorted_matches),
            "Matches": sorted_matches
        }, f, indent=4)
    print(f"✅ Saved loose matches to: {SECONDARY_MATCHES_FILE}")

    # Save the absolute final list of things that STILL didn't match
    with open(FINAL_UNMATCHED_RECIPES, "w") as f:
        sorted_final = dict(sorted(still_unmatched_recipes.items()))
        json.dump({
            "Note": "These survived both Exact Match AND Loose Match passes.",
            "Total_Remaining": len(sorted_final),
            "Unmatched_Items": sorted_final
        }, f, indent=4)
    print(f"✅ Saved truly unmatchable recipe ingredients to: {FINAL_UNMATCHED_RECIPES}")

    # --- SUMMARY ---
    recovery_rate = (len(secondary_matches) / len(unmatched_recipe_items)) * 100 if unmatched_recipe_items else 0
    print(f"\n📊 SECONDARY PASS SUMMARY:")
    print(f"   Recovered Items: {len(secondary_matches)} ({recovery_rate:.1f}% of previously unmatched items)")
    print(f"   Still Unmatched: {len(still_unmatched_recipes)}")


if __name__ == "__main__":
    run_loose_matching_pass()