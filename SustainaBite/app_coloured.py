import streamlit as st
import json
import os
import pandas as pd
import RF_calcsV2
from datetime import date, datetime
from PIL import Image

# --- 1. CONFIGURATION ---
logo_whole = Image.open("Images/SustainaBite whole logo.png")
logo_icon = Image.open("Images/sustainabite logo no background.png")

st.set_page_config(page_title="SustainaBite", page_icon=logo_icon, layout="centered")

# --- CUSTOM THEME (CSS INJECTION) ---
st.markdown("""
<style>
    /* Subtle light mint/slate background for the whole app */
    .stApp {
        background-color: #f4f8f6;
    }

    /* Ensure columns have a transparent background instead of black */
    div[data-testid="column"] {
        background-color: transparent !important;
    }

    /* Make standard text dark grey so it doesn't disappear */
    p, .stMarkdown {
        color: #2E3B42 !important;
    }

    /* Fix the slider and input headings so they are visible and match the theme */
    label {
        color: #4B7484 !important;
        font-weight: 600 !important;
    }

    /* Change all headers (h1, h2, h3) to the Slate Blue from your logo */
    h1, h2, h3 {
        color: #4B7484 !important;
        font-family: 'Helvetica Neue', sans-serif;
    }

    /* Style the buttons to use the Olive Green from your logo */
    div.stButton > button:first-child {
        background-color: #769055;
        color: white;
        border: none;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }

    /* Button hover effect */
    div.stButton > button:first-child:hover {
        background-color: #5c7341;
        box-shadow: 0 6px 8px rgba(0,0,0,0.15);
        color: white;
    }

    /* Style the info and success boxes to match the theme */
    div[data-baseweb="notification"] {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

PANTRY_FILE = "json files/pantry_data.json"
GUI_DB_FILE = "json files/gui_ingredients.json"


# --- 2. DATA LOADING ---
@st.cache_data
def load_ingredient_database():
    if not os.path.exists(GUI_DB_FILE):
        st.error(f"Missing {GUI_DB_FILE}. Please run the prep script.")
        return {}
    with open(GUI_DB_FILE, 'r') as f:
        return json.load(f)


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

raw_options = [f"{name.title()} 🌱" if has_co2 else name.title() for name, has_co2 in master_db.items()]
db_options = sorted(raw_options, key=lambda x: (" 🌱" not in x, x))

# --- 4. BUILD THE UI ---
st.title("SustainaBite: Eco-Smart Dining")
st.write("Track expiration dates to reduce waste and generate low-carbon recipes.")

# --- SECTION: Add Items ---
st.subheader("Add New Item")
st.caption("🌱 = Carbon Tracked Ingredient")

col1, col2 = st.columns([3, 1])

with col1:
    selected_item = st.selectbox("Search Food Item:", options=db_options)

with col2:
    expiry_date = st.date_input("Expiry Date", min_value=date.today())

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
        st.rerun()

# --- SECTION: View Pantry ---
st.divider()
st.subheader("Your Pantry")

if not pantry_items:
    st.info("Your pantry is empty. Add some items above!")
else:
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
            "_raw_name": item['name']
        })

    df = pd.DataFrame(display_data)
    st.dataframe(df.drop(columns=["_raw_name"]), width='stretch', hide_index=True)

# --- NEW: Recipe Customization ---
st.subheader("🎯 Customize Your Meal")

available_tags = [
    "breakfast", "main-meal", "side-dish", "dessert",
    "lunch", "christmas", "vegan", "vegetarian",
    "60-minutes-or-less", "15-minutes-or-less"
]

selected_tags = st.multiselect(
    "Filter by tags (Optional):",
    options=available_tags,
    help="Select tags to narrow down your recipe search. Leave blank for all recipes."
)

user_threshold_pct = st.slider(
    "Carbon Data Strictness (%)",
    min_value=30,
    max_value=100,
    value=70,
    step=5,
    help="Higher % means more accurate carbon scores, but fewer recipe options. Lower % gives more options but allows un-tracked ingredients."
)
decimal_threshold = user_threshold_pct / 100.0

st.write("")

user_min_ingredients = st.slider(
    "Minimum Number of Ingredients",
    min_value=1,
    max_value=43,
    value=6,
    step=1,
    help="More ingredients means a more complex recipe"
)

min_num_ingredients = user_min_ingredients

st.write("")

col_remove, col_gen = st.columns(2)

with col_remove:
    safe_options = [i.get('display_name', i.get('name', '').title()) for i in pantry_items]
    items_to_remove = st.multiselect("Select items to remove:", options=safe_options)

    if st.button("🗑️ Remove Selected"):
        if items_to_remove:
            pantry_items = [i for i in pantry_items if
                            i.get('display_name', i.get('name', '').title()) not in items_to_remove]
            save_pantry(pantry_items)
            st.rerun()

with col_gen:
    st.write("")

    if st.button("🍳 Generate Low-Carbon Recipes", width='stretch'):
        with st.spinner(f"Analyzing recipes for your pantry..."):

            RF_calcsV2.calculate_top_recipes(
                required_tags=selected_tags,
                min_match_threshold=decimal_threshold,
                min_ingredients=min_num_ingredients
            )

            results_file = "json files/top_50_low_carbon_recipes.json"
            if os.path.exists(results_file):
                with open(results_file, "r") as f:
                    top_recipes = json.load(f)
            else:
                top_recipes = []

        if not top_recipes:
            st.error("No recipes found that match your ingredients and tags. Try removing some filters!")
        else:
            st.success("✅ Recipes generated successfully!")
            st.divider()

            st.subheader("🏆 Your Top Sustainable Meals")
            st.caption("Meals are ranked by lowest carbon footprint. Ingredients you own count as 0 kg CO2e!")

            for i, recipe in enumerate(top_recipes[:10], 1):

                card_title = f"#{i} - {recipe['title']} ({recipe['total_co2']} kg CO2e)"

                with st.expander(card_title):
                    st.write(f"**Calories:** {recipe['kcal']} kcal")
                    st.write(f"**Data Coverage:** {recipe['match_ratio'] * 100:.1f}%")

                    st.markdown("### 🛒 Ingredients")
                    for matched in recipe['matched_items']:
                        if "[PANTRY" in matched:
                            st.markdown(f"- 🟢 **{matched}**")
                        else:
                            st.markdown(f"- ⚪ {matched}")

                    if recipe['unmatched_items']:
                        st.markdown("### ❓ Missing Data (Not Scored)")
                        st.caption("These items were in the recipe but aren't in our carbon database.")
                        for unmatched in recipe['unmatched_items']:
                            st.markdown(f"- ❌ {unmatched}")