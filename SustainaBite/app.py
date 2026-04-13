import streamlit as st
import json
import os
import pandas as pd
import RF_calcsV3
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
def cached_single_recipe(pantry_data, target_meal, threshold, tags, min_ing, rating):
    return RF_calcsV3.generate_single_recipe_options(
        pantry_data=pantry_data,
        target_tag=target_meal,
        min_match_threshold=threshold,
        user_tags=tags,
        min_ingredients=min_ing,
        top_n=50, # <-- We tell the engine to grab the top 50!
        min_rating=rating
    )

def load_pantry():
    if not os.path.exists(PANTRY_FILE):
        return []
    with open(PANTRY_FILE, 'r') as f:
        return json.load(f)


def save_pantry(data):
    os.makedirs(os.path.dirname(PANTRY_FILE), exist_ok=True)
    with open(PANTRY_FILE, 'w') as f:
        json.dump(data, f, indent=4)


# --- 3. PREPARE DATA ---
master_db = load_ingredient_database()
pantry_items = load_pantry()

# Build the dropdown options (CO2 items get a 🌱 and are sorted to the top)
raw_options = [f"{name.title()} 🌱" if has_co2 else name.title() for name, has_co2 in master_db.items()]
db_options = sorted(raw_options, key=lambda x: (" 🌱" not in x, x))

# --- 4. BUILD THE UI ---
st.title("SustainaBite: Eco-Smart Dining")
st.write("Track expiration dates to reduce waste and generate low-carbon recipes.")

# --- SECTION: Add Items ---
st.subheader("Add New Item")
st.caption("🌱 = Carbon Tracked Ingredient")

# Streamlit columns make layout easy
col1, col2 = st.columns([3, 1])

with col1:
    # This single line creates a perfect, fast, auto-completing search bar
    selected_item = st.selectbox("Search Food Item:", options=db_options)

with col2:
    expiry_date = st.date_input("Expiry Date", min_value=date.today())

# The Add Button
if st.button("➕ Add to Pantry", type="primary"):
    if selected_item:
        clean_name = selected_item.replace(" 🌱", "").lower()

        new_item = {
            "name": clean_name,
            "display_name": selected_item,
            "date": expiry_date.strftime("%Y-%m-%d")
        }
        pantry_items.append(new_item)
        save_pantry(pantry_items)
        st.success(f"Added **{selected_item}** to your pantry!")
        st.rerun()  # Refreshes the app instantly to show the new item

# --- SECTION: View Pantry ---
st.divider()
st.subheader("Your Pantry")

if not pantry_items:
    st.info("Your pantry is empty. Add some items above!")
else:
    # Process pantry data for a beautiful display table
    display_data = []
    today = date.today()

    for item in pantry_items:
        exp_date = datetime.strptime(item['date'], "%Y-%m-%d").date()
        delta = (exp_date - today).days

        if delta < 0:
            status = "🚨 EXPIRED"
        elif delta == 0:
            status = "⚠️ Expires Today!"
        elif delta <= 3:
            status = "🟠 Use Soon"
        else:
            status = "✅ Fresh"

        display_data.append({
            "Food Item": item.get('display_name', item['name'].title()),
            "Expiry Date": item['date'],
            "Days Left": delta,
            "Status": status,
            "_raw_name": item['name']  # Hidden field for exact matching later
        })

    # Convert to Pandas DataFrame for native, sortable tables in Streamlit
    df = pd.DataFrame(display_data)

    # Display the table (dropping the hidden raw name column for the UI)
    st.dataframe(df.drop(columns=["_raw_name"]), use_container_width=True, hide_index=True)

# --- SECTION: Remove Items ---
# We removed the column container completely. These will naturally be full-width!
safe_options = [i.get('display_name', i.get('name', '').title()) for i in pantry_items]
items_to_remove = st.multiselect("Select items to remove:", options=safe_options)

if st.button("🗑️ Remove Selected"):
    if items_to_remove:
        pantry_items = [i for i in pantry_items if
                        i.get('display_name', i.get('name', '').title()) not in items_to_remove]
        save_pantry(pantry_items)
        st.rerun()


# --- Recipe Customization ---
st.subheader("🎯 Customize Your Meal")

available_tags = load_available_tags()

selected_tags = st.multiselect(
    "Filter by tags (Optional):",
    options=available_tags,
    help="Select tags to narrow down your recipe search. leave blank for all recipes."
)

# --- The Threshold Slider ---
user_threshold_pct = st.slider(
    "Carbon Data Strictness (%)",
    min_value=30,
    max_value=100,
    value=70,
    step=5,
    help="Higher % means more accurate carbon scores, but fewer recipe options. Lower % gives more options but allows un-tracked ingredients."
)
# Convert percentage (70) to decimal (0.70) for the backend math
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

# --- SECTION: Generate Generation Modes ---
st.divider()
st.subheader("⚙️ Generation Engine")


# --- HELPER FUNCTION TO DRAW THE MEAL CARDS ---
def draw_meal_card(meal_title, recipe_data):
    if not recipe_data:
        st.warning(f"Could not find a valid {meal_title} for this criteria.")
        return

    st.markdown(f"#### {meal_title}: {recipe_data['title']}")
    with st.expander(f"View Recipe & Data ({recipe_data['total_co2']} kg CO2e)"):

        # --- NEW: Nutritional Display ---
        nut = recipe_data.get('nutrition', {})
        st.markdown(
            f"**🔥 Calories:** {nut.get('calories', 0)} kcal | **Coverage:** {recipe_data['match_ratio'] * 100:.1f}%")

        # Streamlit columns to create a neat "Macro Bar"
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Protein", f"{nut.get('protein', 0)}g")
        m2.metric("Carbs", f"{nut.get('carbs', 0)}g")
        m3.metric("Fat", f"{nut.get('total_fat', 0)}g")
        m4.metric("Sugar", f"{nut.get('sugar', 0)}g")
        st.divider()

        # --- NEW: Ingredients & Instructions Layout ---
        col_ing, col_inst = st.columns([1, 1.5])  # Makes instructions slightly wider

        with col_ing:
            st.markdown("##### 🛒 Ingredients")
            for matched in recipe_data['matched_items']:
                if "EXPIRING" in matched:
                    st.markdown(f"- 🚨 **{matched}**")
                elif "PANTRY" in matched:
                    st.markdown(f"- 🟢 **{matched}**")
                else:
                    st.markdown(f"- ⚪ {matched}")

            if recipe_data['unmatched_items']:
                st.markdown("##### ❓ Missing Data")
                for unmatched in recipe_data['unmatched_items']:
                    st.markdown(f"- ❌ {unmatched}")

        with col_inst:
            st.markdown("##### 🍳 Instructions")
            instructions = recipe_data.get('instructions', [])
            if not instructions:
                st.write("*No instructions provided.*")
            else:
                for step_num, step_text in enumerate(instructions, 1):
                    # Capitalize the first letter of each step so it looks clean
                    clean_step = str(step_text).strip().capitalize()
                    st.markdown(f"**{step_num}.** {clean_step}")


# Create the 3 tabs for different generation modes
tab_7day, tab_1day, tab_single = st.tabs(["📅 7-Day Plan", "☀️ 1-Day Plan", "🍽️ Single Meal"])

# --- MODE 1: 7-DAY PLAN ---
with tab_7day:
    st.write("Generate a full week of meals optimized to reduce food waste.")
    if st.button("Generate 7-Day Plan", use_container_width=True, type="primary"):
        with st.spinner("Optimizing 7-day menu..."):
            plan_7d = RF_calcsV3.generate_meal_plan(pantry_items, decimal_threshold, selected_tags, user_min_ingredients,
                                                    days=7, min_rating=user_min_rating)

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
        with st.spinner("Optimizing today's menu..."):
            plan_1d = RF_calcsV3.generate_meal_plan(pantry_items, decimal_threshold, selected_tags, user_min_ingredients,
                                                    days=1, min_rating=user_min_rating)

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
                               ["main-meal", "breakfast", "lunch", "dessert", "side-dish", "snack"])

    # When they search for a new meal type, we reset the memory back to the top 5
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
                min_ing=user_min_ingredients,
                rating=user_min_rating
            )

        if single_options_pool:
            # Grab the current offset number (e.g., 0, 5, 10...)
            offset = st.session_state.recipe_offset

            # If they refresh so many times they run out of recipes, loop back to the start!
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

            # --- NEW: The Refresh Button ---
            st.write("")  # Spacing
            if len(single_options_pool) > 5:
                if st.button("🔄 I don't like these, show me 5 different meals", use_container_width=True):
                    # Add 5 to the offset and instantly reload the page!
                    st.session_state.recipe_offset += 5
                    st.rerun()
        else:
            st.error("No recipes found. Try lowering strictness or removing filters.")