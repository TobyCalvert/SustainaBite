import streamlit as st
import json
import os
import pandas as pd
import backend_engines
import gensim
import time
from datetime import date, datetime, timedelta
from PIL import Image

# --- 1. CONFIGURATION ---
logo_whole = Image.open("Images/SustainaBite whole logo.png")
logo_icon = Image.open("Images/sustainabite logo no background.png")

st.set_page_config(page_title="SustainaBite", page_icon=logo_icon, layout="centered")

if "recipe_offset" not in st.session_state:
    st.session_state.recipe_offset = 0

PANTRY_FILE = "json files/pantry_data.json"
GUI_DB_FILE = "json files/gui_ingredients.json"


# --- 2. DATA LOADING ---
# @st.cache_data tells Streamlit to load this massive 14,000 item file ONCE and remember it.
@st.cache_data
def load_ingredient_database():
    if not os.path.exists(GUI_DB_FILE):
        st.error(f"Missing {GUI_DB_FILE}. Please run the prep script.")
        return {}
    with open(GUI_DB_FILE, 'r') as f:
        return json.load(f)

@st.cache_data
def load_available_tags():
    tag_file = "json files/unique_tags.json"
    if not os.path.exists(tag_file):
        return ["breakfast", "lunch", "main-meal"] # Fallback just in case
    with open(tag_file, 'r') as f:
        return json.load(f)

# ---Cached Wrapper for Single Recipes ---
@st.cache_data(show_spinner=False)
def cached_single_recipe(pantry_data, target_meal, threshold=0.70, tags=None, excluded_tags=None, min_ing=6, rating=0.0, auto_swap_enabled=False):
    return backend_engines.generate_single_recipe_options(
        pantry_data=pantry_data,
        target_tag=target_meal,
        min_match_threshold=threshold,
        user_tags=tags,
        excluded_tags=excluded_tags,
        min_ingredients=min_ing,
        top_n=50,
        min_rating=rating,
        auto_swap=auto_swap_enabled
    )

# --- Load the Smart Substitution Engine ---
@st.cache_resource(show_spinner=False)
def load_w2v_model():
    model_path = "Data/archive/ingredient_w2v.model"
    if os.path.exists(model_path):
        return gensim.models.Word2Vec.load(model_path)
    return None

w2v_model = load_w2v_model()

# --- Load the Pantry ---
def load_pantry():
    if not os.path.exists(PANTRY_FILE):
        return []
    with open(PANTRY_FILE, 'r') as f:
        return json.load(f)

def save_pantry(data):
    os.makedirs(os.path.dirname(PANTRY_FILE), exist_ok=True)
    with open(PANTRY_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- Load Tips ---
def load_tips():
    try:
        with open("json files/tips.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# --- Load Impact Stats ---
def load_impact_stats():
    try:
        with open("json files/impact_stats.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): # <-- Catch both errors!
        # If the file is missing OR empty, return the default starting stats
        return {"methane_produced_kg": 0.0, "methane_prevented_kg": 0.0}

def save_impact_stats(stats):
    with open("json files/impact_stats.json", "w") as f:
        json.dump(stats, f, indent=4)

# --- Load Regrow Guides ---
def load_regrow_guides():
    try:
        with open("json files/regrow_guides.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# --- 3. PREPARE DATA ---
master_db = load_ingredient_database()
pantry_items = load_pantry()
zero_waste_tips = load_tips()
user_impact = load_impact_stats()
zero_waste_guides = load_regrow_guides()

# Build the dropdown options (CO2 items get a 🌱 and are sorted to the top)
raw_options = [f"{name.title()} 🌱" if has_co2 else name.title() for name, has_co2 in master_db.items()]
db_options = sorted(raw_options, key=lambda x: (" 🌱" not in x, x))

# --- 4. BUILD THE UI ---
st.title("SustainaBite: Eco-Smart Dining")
st.write("Track expiration dates to reduce waste and generate low-carbon recipes.")

# --- SECTION 1: Add New Item ---
st.subheader("Add New Item")
st.caption("🌱 = Carbon Tracked Ingredient")

with st.form("add_item_form"):

    # --- ROW 1 (The Top Inputs) ---
    col1, col2 = st.columns(2)

    with col1:
        st.write("Search Food Item:")
        item_to_add = st.selectbox(
            label="Search Food Item:",
            label_visibility="collapsed",
            options=db_options
        )

    with col2:
        st.write("") # Blank space for vertical alignment
        st.write("")
        st.write("")
        is_staple = st.checkbox("♾️ Staple Supply", help="Tick this for staples like salt or oil that won't run out.")

    # --- ROW 2 (The Bottom Inputs) ---
    col3, col4 = st.columns(2)

    with col3:
        st.write("Quantity (Servings):")
        qty = st.number_input(
            label="Quantity (Servings):",
            label_visibility="collapsed",
            min_value=1,
            value=1,
            step=1
        )

    with col4:
        st.write("Expiry Date:")
        exp_date = st.date_input(
            label="Expiry Date:",
            label_visibility="collapsed", # Hide the built-in label
            value=date.today()
        )

    # --- Add to Pantry Button ---
    add_btn = st.form_submit_button("➕ Add to Pantry", type="primary")

if add_btn:
    if item_to_add:
        clean_name = item_to_add.replace(" 🌱", "").lower()

        date_str = "N/A" if is_staple else exp_date.strftime("%Y-%m-%d")

        new_item = {
            "name": clean_name,
            "display_name": item_to_add,
            "date": date_str,
            "quantity": qty,
            "is_infinite": is_staple
        }

        pantry_items.append(new_item)
        save_pantry(pantry_items)
        st.success(f"Added {qty if not is_staple else '∞'}x {item_to_add} to your pantry!")

        tip_found = False

        for tip in zero_waste_tips:
            if any(keyword in clean_name for keyword in tip["keywords"]):
                st.toast(tip["message"], icon=tip.get("icon", "💡"))
                time.sleep(5)
                tip_found = True
                break

        if not tip_found:
            time.sleep(1)

        st.rerun()

# --- SECTION 1.5: End of Life / Waste Resolution UI ---
today = date.today()
expired_items = []

for idx, item in enumerate(pantry_items):
    if not item.get('is_infinite', False):
        try:
            exp_date_obj = datetime.strptime(item['date'], "%Y-%m-%d").date()
            if (exp_date_obj - today).days < 0:
                expired_items.append((idx, item))
        except:
            pass

if expired_items:
    st.error("🚨 **Action Required: Expired Food Detected!**")
    st.write("Some items in your pantry have expired. How did you dispose of them?")

    for idx, item in expired_items:
        # Create a mini layout for each expired item
        col_text, col_bin, col_compost = st.columns([2, 1, 1])

        with col_text:
            st.write(f"**{item['quantity']}x {item['display_name']}**")

        with col_bin:
            if st.button("🗑️ Threw in Bin", key=f"bin_{idx}"):
                # 1. Ask the backend to calculate the weight
                est_kg_per_serving = backend_engines.estimate_serving_kg(item['name'])
                total_kg = est_kg_per_serving * float(item.get('quantity', 1))

                # 2. Add to Methane PRODUCED (0.07 IPCC 2019 Factor)
                user_impact["methane_produced_kg"] += (total_kg * 0.07)
                save_impact_stats(user_impact)

                # 3. Delete from pantry and refresh
                pantry_items.pop(idx)
                save_pantry(pantry_items)
                st.rerun()

        with col_compost:
            if st.button("🌱 Composted", key=f"comp_{idx}"):
                # 1. Ask the backend to calculate the weight
                est_kg_per_serving = backend_engines.estimate_serving_kg(item['name'])
                total_kg = est_kg_per_serving * float(item.get('quantity', 1))

                # 2. Add to Methane PREVENTED (0.07 IPCC 2019 Factor)
                user_impact["methane_prevented_kg"] += (total_kg * 0.07)
                save_impact_stats(user_impact)

                # 3. Delete from pantry and refresh
                pantry_items.pop(idx)
                save_pantry(pantry_items)
                st.rerun()

# --- SECTION 2: View Pantry ---
st.divider()
st.subheader("Your Pantry")

if not pantry_items:
    st.info("Your pantry is empty. Add some items above!")
else:
    # Process pantry data for a beautiful display table
    display_data = []
    today = date.today()

    for item in pantry_items:
        # Get the flag, default to False if it doesn't exist
        is_inf = item.get('is_infinite', False)

        if is_inf:
            status = "♾️ Staple"
            delta_str = "∞"
            display_date = "N/A"
            qty_str = "∞"
        else:
            try:
                exp_date_obj = datetime.strptime(item['date'], "%Y-%m-%d").date()
                delta_int = (exp_date_obj - today).days

                if delta_int < 0:
                    status = "🚨 EXPIRED"
                elif delta_int == 0:
                    status = "⚠️ Expires Today!"
                elif delta_int <= 3:
                    status = "🟠 Use Soon"
                else:
                    status = "✅ Fresh"

                # Force PyArrow compliance by converting the int to a string
                delta_str = str(delta_int)
                display_date = item['date']
            except:
                status = "❓ Error"
                delta_str = "N/A"
                display_date = "N/A"

            # Force PyArrow compliance for quantity
            qty_str = str(item.get('quantity', 1))

        display_data.append({
            "Food Item": item.get('display_name', item['name'].title()),
            "Quantity": qty_str,
            "Expiry Date": display_date,
            "Days Left": delta_str,
            "Status": status,
            "_raw_name": item['name']
        })

    # Convert to Pandas DataFrame for native, sortable tables in Streamlit
    df = pd.DataFrame(display_data)

    # Display the table (dropping the hidden raw name column for the UI)
    st.dataframe(df.drop(columns=["_raw_name"]), use_container_width=True, hide_index=True)

# --- Remove Items ---
# We removed the column container completely. These will naturally be full-width!
safe_options = [i.get('display_name', i.get('name', '').title()) for i in pantry_items]
items_to_remove = st.multiselect("Select items to remove:", options=safe_options)

if st.button("🗑️ Remove Selected"):
    if items_to_remove:
        pantry_items = [i for i in pantry_items if
                        i.get('display_name', i.get('name', '').title()) not in items_to_remove]
        save_pantry(pantry_items)
        st.rerun()


# --- SECTION 3: Recipe Customisation ---
st.subheader("🎯 Customise Your Meal")

available_tags = load_available_tags()

# --- TAG FILTERING ---
st.write("Dietary Preferences & Exclusions")
col_inc, col_exc = st.columns(2)

with col_inc:
    selected_tags = st.multiselect(
        "✅ Must Include",
        options=available_tags,
        help="Recipes MUST contain all of these tags."
    )

with col_exc:
    excluded_tags = st.multiselect(
        "❌ Must Exclude",
        options=available_tags,
        help="Recipes containing ANY of these tags will be instantly removed."
    )

if set(selected_tags) & set(excluded_tags):
    st.warning("⚠️ You have the same tag in both Include and Exclude boxes. Please remove one!")

# --- The Threshold Slider ---
user_threshold_pct = st.slider(
    "Carbon Data Strictness (%)",
    min_value=30,
    max_value=100,
    value=70,
    step=5,
    help="Higher % means more accurate carbon scores, but fewer recipe options. Lower % gives more options but allows un-tracked ingredients."
)
decimal_threshold = user_threshold_pct / 100.0

st.write("")  # Spacing

user_min_ingredients = st.slider(
    "Minimum Number of Ingredients",
    min_value=1,
    max_value=43,
    value=6,
    step=1,
    help="More ingredients means a more complex recipe"
)

st.write("")  # Spacing

user_min_rating = st.slider(
    "Minimum Recipe Rating ⭐",
    min_value=0.0,
    max_value=5.0,
    value=0.0,
    step=0.5,
    help="Filter out recipes with low user ratings. Set to 0 to include unrated recipes."
)

st.write("")

#automatic smart swap
auto_swap_enabled = st.checkbox("🔄 Auto-Swap Ingredients",
                                help="If enabled, the engine will automatically substitute missing ingredients with mathematically similar items you already own, calculating the meal at 0 CO2 for that item.")

# --- SECTION 4: Generate Generation Modes ---
st.divider()
st.subheader("⚙️ Generation Engine")


# --- HELPER FUNCTION TO DRAW THE MEAL CARDS ---
def draw_meal_card(meal_title, recipe_data):
    if not recipe_data:
        st.warning(f"Could not find a valid {meal_title} for this criteria.")
        return

    st.markdown(f"#### {meal_title}: {recipe_data['title']}")
    with st.expander(f"View Recipe & Data ({recipe_data['total_co2']} kg CO2e)"):

        # --- Smart Rating Display ---
        nut = recipe_data.get('nutrition', {})
        recipe_rating = recipe_data.get('rating', 0.0)
        formatted_rating = f"{recipe_rating:.1f}"
        is_predicted = recipe_data.get('is_predicted', False)

        # Check if the ML model predicted this score, or if humans rated it
        if is_predicted:
            rating_text = f"🤖 **{formatted_rating}/5.0** (ML Predicted)"
        else:
            if recipe_rating > 0:
                rating_text = f"⭐ **{formatted_rating}/5.0** (User Rated)"
            else:
                rating_text = "⚪ **Unrated**"  # Just in case a 0.0 slips through

        # Display the dynamic rating alongside the calories and coverage
        st.markdown(
            f"{rating_text} | **🔥 Calories:** {nut.get('calories', 0)} kcal | **Coverage:** {recipe_data['match_ratio'] * 100:.1f}%")

        # Streamlit columns to create a neat "Macro Bar"
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Protein", f"{nut.get('protein', 0)}g")
        m2.metric("Carbs", f"{nut.get('carbs', 0)}g")
        m3.metric("Fat", f"{nut.get('total_fat', 0)}g")
        m4.metric("Sugar", f"{nut.get('sugar', 0)}g")
        st.divider()

        # --- Categorise Ingredients by Actionable State ---
        in_pantry = []
        to_buy = []

        # 1. Parse the matched items
        for matched in recipe_data.get('matched_items', []):
            if "PANTRY" in matched or "EXPIRING" in matched or "STAPLE" in matched or "SWAP" in matched:
                in_pantry.append(matched)
            else:
                # It has a carbon score, but the user doesn't own it.
                orig_ing = matched.split(" -> ")[0]
                to_buy.append({"display": f"{orig_ing} 🌱", "search_term": orig_ing})

        # 2. Parse the missing/unmatched items
        for unmatched in recipe_data.get('unmatched_items', []):
            # No carbon score, and the user doesn't own it.
            to_buy.append({"display": f"{unmatched} ❓", "search_term": unmatched})

        # --- UI Layout ---
        col_ing, col_inst = st.columns([1, 1.5])

        with col_ing:
            # --- SECTION 1: What they already own ---
            st.markdown("##### 🏡 In Your Pantry")
            if not in_pantry:
                st.write("*None*")
            else:
                for item in in_pantry:
                    st.markdown(f"- **{item}**")

            st.write("")  # Spacer

            # --- SECTION 2: The Shopping List & Smart Swaps ---
            st.markdown("##### 🛒 Ingredients to Buy")
            if not to_buy:
                st.success("*You have everything you need!*")
            else:
                for item in to_buy:
                    st.markdown(f"- ⚪ {item['display']}")

                    # --- Smart Substitution Logic for ALL missing items ---
                    if w2v_model:
                        clean_unmatched = backend_engines.standardize_ingredient(item['search_term'])

                        if clean_unmatched in w2v_model.wv:
                            similars = w2v_model.wv.most_similar(clean_unmatched, topn=15)

                            pantry_std = [backend_engines.standardize_ingredient(p.get("name", "")) for p in pantry_items]
                            owned_subs = [sim[0].title() for sim in similars if sim[0] in pantry_std]

                            if owned_subs:
                                st.caption(
                                    f"&nbsp;&nbsp;&nbsp;&nbsp;💡 **Pantry Match!** Swap with your: **{', '.join(owned_subs)}**")
                            else:
                                general_subs = [sim[0].title() for sim in similars[:3]]
                                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;💡 *Try swapping with: {', '.join(general_subs)}*")

        with col_inst:
            # --- SECTION 3: Instructions ---
            st.markdown("##### 🍳 Instructions")
            instructions = recipe_data.get('instructions', [])
            if not instructions:
                st.write("*No instructions provided.*")
            else:
                for step_num, step_text in enumerate(instructions, 1):
                    clean_step = str(step_text).strip().capitalize()
                    st.markdown(f"**{step_num}.** {clean_step}")


# Create the 3 tabs for different generation modes
tab_7day, tab_1day, tab_single, tab_impact = st.tabs(["📅 7-Day Plan", "☀️ 1-Day Plan", "🍽️ Single Meal", "🌍 My Impact"])

# --- MODE 1: 7-DAY PLAN ---
with tab_7day:
    st.write("Generate a full week of meals optimised to reduce food waste.")
    if st.button("Generate 7-Day Plan", use_container_width=True, type="primary"):
        with st.spinner("Optimising 7-day menu..."):
            plan_7d = backend_engines.generate_meal_plan(pantry_items, decimal_threshold, selected_tags, excluded_tags, user_min_ingredients,
                                                    days=7, min_rating=user_min_rating, auto_swap=auto_swap_enabled)

        if plan_7d:
            st.success("✅ 7-Day Plan generated!")
            current_date = date.today()
            day_labels = [(current_date + timedelta(days=i)).strftime("%A, %b %d") for i in range(7)]
            day_tabs = st.tabs(day_labels)

            weekly_co2 = 0
            for i, d_tab in enumerate(day_tabs):
                with d_tab:
                    day_data = plan_7d[i]
                    daily_co2 = sum([day_data[m]['total_co2'] for m in ["Breakfast", "Lunch", "Dinner"] if day_data[m]])
                    weekly_co2 += daily_co2
                    st.metric("Daily Carbon Footprint", f"{round(daily_co2, 2)} kg CO2e")
                    draw_meal_card("🌅 Breakfast", day_data["Breakfast"])
                    draw_meal_card("🥪 Lunch", day_data["Lunch"])
                    draw_meal_card("🍝 Dinner", day_data["Dinner"])
            st.metric("🌍 Total Weekly Carbon Footprint", f"{round(weekly_co2, 2)} kg CO2e")
        else:
            st.error("Failed to generate. Try lowering strictness.")

# --- MODE 2: 1-DAY PLAN ---
with tab_1day:
    st.write("Generate a Breakfast, Lunch, and Dinner for today.")
    if st.button("Generate 1-Day Plan", use_container_width=True, type="primary"):
        with st.spinner("Optimising today's menu..."):
            plan_1d = backend_engines.generate_meal_plan(pantry_items, decimal_threshold, selected_tags, excluded_tags, user_min_ingredients,
                                                    days=1, min_rating=user_min_rating, auto_swap=auto_swap_enabled)

        if plan_1d:
            st.success("✅ Today's Plan generated!")
            day_data = plan_1d[0]
            daily_co2 = sum([day_data[m]['total_co2'] for m in ["Breakfast", "Lunch", "Dinner"] if day_data[m]])
            st.metric("Today's Carbon Footprint", f"{round(daily_co2, 2)} kg CO2e")
            draw_meal_card("🌅 Breakfast", day_data["Breakfast"])
            draw_meal_card("🥪 Lunch", day_data["Lunch"])
            draw_meal_card("🍝 Dinner", day_data["Dinner"])
        else:
            st.error("Failed to generate. Try lowering strictness.")

# --- MODE 3: SINGLE RECIPE ---
with tab_single:
    st.write("Find the best individual meals based on your pantry.")

    target_meal = st.selectbox("What are you looking for?",
                               ["main-dish", "breakfast", "lunch", "desserts", "side-dishes", "snacks"])

    # When they search for a new meal type, reset the memory back to the top 5
    if st.button("🔍 Find Meals", use_container_width=True, type="primary"):
        st.session_state.recipe_offset = 0
        st.session_state.has_searched = True  # Flag to show results

    # Only render the results if they have clicked the search button
    if st.session_state.get("has_searched", False):
        with st.spinner(f"Finding the best {target_meal}s..."):

            # This runs the math ONCE and caches the top 50
            single_options_pool = cached_single_recipe(
                pantry_data=pantry_items,
                target_meal=target_meal,
                threshold=decimal_threshold,
                tags=selected_tags,
                excluded_tags=excluded_tags,
                min_ing=user_min_ingredients,
                rating=user_min_rating,
                auto_swap_enabled=auto_swap_enabled
            )

        if single_options_pool:
            # Grab the current offset number (e.g., 0, 5, 10...)
            offset = st.session_state.recipe_offset

            # If they refresh so many times they run out of recipes, loop back to the start
            if offset >= len(single_options_pool):
                st.session_state.recipe_offset = 0
                offset = 0
                st.info("You've seen all the options! Looping back to the top.")

            # Slice the master list to get just 5 meals
            display_options = single_options_pool[offset: offset + 5]
            st.success(f"✅ Showing options {offset + 1} to {offset + len(display_options)}!")

            # Draw the 5 meal cards
            for i, recipe in enumerate(display_options, offset + 1):
                draw_meal_card(f"Option #{i}", recipe)

            # --- The Refresh Button ---
            st.write("")  # Spacing
            if len(single_options_pool) > 5:
                if st.button("🔄 I don't like these, show me 5 different meals", use_container_width=True):
                    # Add 5 to the offset and instantly reload the page!
                    st.session_state.recipe_offset += 5
                    st.rerun()
        else:
            st.error("No recipes found. Try lowering strictness or removing filters.")

with tab_impact:

    # --- ROW 1: Gamified Metrics ---
    # Calculate CO2e equivalents (Methane is 28x worse)
    ch4_prevented = user_impact["methane_prevented_kg"]
    co2_prevented = ch4_prevented * 28.0

    ch4_produced = user_impact["methane_produced_kg"]
    co2_produced = ch4_produced * 28.0

    st.header("Your Environmental Impact")
    st.write("Tracking your journey towards a Zero-Waste kitchen.")

    m1, m2 = st.columns(2)
    m1.metric(
        label="✅ Methane Prevented (Composting)",
        value=f"{ch4_prevented:.2f} kg",
        delta=f"Saved {co2_prevented:.1f} kg CO2e",
        delta_color="normal"
    )

    #inverse delta color so that PRODUCING methane shows up in Red
    m2.metric(
        label="❌ Methane Produced (Landfill)",
        value=f"{ch4_produced:.2f} kg",
        delta=f"Generated {co2_produced:.1f} kg CO2e",
        delta_color="inverse"
    )
    
    st.divider()

    # --- ROW 2: The "Regrow" Guides (Dynamic JSON Integration) ---
    st.subheader("🌱 Grow It Back!")
    st.write("We noticed you have some items in your pantry that you can magically regrow from scraps.")

    # Get a list of all current pantry ingredient names
    pantry_names = [p['name'].lower() for p in pantry_items]

    # Find all guides in the JSON that match the user's current pantry
    unlocked_guides = []
    for guide in zero_waste_guides:
        # Check if ANY keyword in the guide matches ANY item in the pantry
        if any(any(keyword in p_name for keyword in guide["keywords"]) for p_name in pantry_names):
            unlocked_guides.append(guide)

    # Display logic
    if not unlocked_guides:
        st.info(
            "💡 Add items like **Green Onions, Celery, Potatoes, or Garlic** to your pantry to unlock zero-waste regrow guides!")
    else:
        # Create a dynamic 2-column grid layout so it always looks neat
        cols = st.columns(2)

        for i, guide in enumerate(unlocked_guides):
            # Alternates drawing between the left and right columns
            with cols[i % 2]:
                with st.expander(guide.get("title", "Regrow Guide")):
                    if "intro" in guide:
                        st.write(guide["intro"])

                    # Automatically number and print the steps
                    for step_num, step_text in enumerate(guide.get("steps", []), 1):
                        st.write(f"**{step_num}.** {step_text}")

                    if "outro" in guide:
                        st.write(guide["outro"])
    st.divider()

    # --- ROW 1.5: The Native Composting Guide ---
    st.subheader("♻️ How to Start Composting")
    st.write(
        "You are preventing methane by clicking 'Composted', but how do you actually do it at home? It is easier than you think!")

    with st.expander("📖 Open the Beginner's Guide to Home Composting"):
        # Use columns to make the text highly readable
        col_guide1, col_guide2 = st.columns(2)

        with col_guide1:
            st.markdown("#### 1. Choose Your Bin")
            st.write(
                "You don't need a massive garden. If you have a yard, a standard outdoor compost bin (or just a designated pile) works great. If you live in an apartment, look into **Bokashi bins** or **Worm Composters (Vermiculture)** which fit under the sink and produce zero odors.")

            st.markdown("#### 2. The Golden Ratio (Greens vs. Browns)")
            st.write(
                "Composting is a science. Microbes need a balance of Nitrogen (Greens) and Carbon (Browns) to break down food aerobically without smelling bad. Aim for a ratio of roughly **50% Greens and 50% Browns** by volume.")

        with col_guide2:
            st.markdown("#### 3. What to put in:")
            st.markdown("""
                * **🟢 GREENS (Nitrogen-rich):** Fruit/veg scraps, coffee grounds, tea bags, grass clippings.
                * **🟤 BROWNS (Carbon-rich):** Cardboard (uncoated), paper, dry leaves, egg cartons, sawdust.
                * **❌ DO NOT COMPOST:** Meat, dairy, bones, or oils (these attract pests and create anaerobic rot).
                """)

            st.markdown("#### 4. Maintenance")
            st.write(
                "**Air and Water:** The microbes need oxygen. Turn or stir your pile once a week to aerate it. It should feel like a 'wrung-out sponge'—if it's too dry, add a splash of water. If it's too wet and smells, add more Browns (cardboard) to soak up the moisture.")

        st.success(
            "🌟 **The Result:** In 3 to 6 months, your waste will transform into rich, dark soil (humus) that you can use to grow your regrown kitchen scraps!")

    # --- ROW 3: The "Ugly Food" Reality Check ---
    st.subheader("The 'Ugly Food' Epidemic")
    st.write(
        "Did you know that nearly **30% of all agricultural produce** is discarded before it even hits the supermarket simply because it doesn't look 'perfect'?")
    st.info(
        "Next time you shop, look for the 'Wonky' or 'Imperfect' veg boxes. They cost less, taste exactly the same, and buying them directly fights agricultural food waste!")