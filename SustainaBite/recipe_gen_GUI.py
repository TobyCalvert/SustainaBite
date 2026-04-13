import tkinter as tk
from tkinter import messagebox, simpledialog
import requests
import json
import threading

# --- 1. API Setup and Data ---

# NOTE: The provided API key is visible here. In a real-world application,
# this should be stored securely (e.g., environment variables).
API_URL = "https://api.climatiq.io/data/v1/estimate"
API_HEADERS = {"Authorization": "Bearer 3AE36XTBJH7SS3J96D6KXNAVZM"}

# Available foods and emission categories (trimmed for brevity in the GUI list)
FOOD_EMISSION_FACTORS = {
    # FRUITS
    "apple_raw_all_varieties": "food-type_apple_raw_all_varieties",
    "banana_raw": "food-type_banana_raw",
    "avocado_raw": "food-type_avocado_raw",
    "grapefruit_raw": "food-type_grapefruit_raw",

    # VEGETABLES
    "broccoli_raw": "food-type_broccoli_raw",
    "carrot_raw": "food-type_carrot_raw",
    "garlic_raw": "food-type_garlic_raw",
    "cucumber_raw": "food-type_cucumber_raw",

    # LEGUMES & GRAINS
    "black_beans": "food-type_black_beans",
    "chickpea_canned": "food-type_chickpea_canned",
    "barley_groats_raw": "food-type_barley_groats_raw",

    # MEATS
    "beef": "food-type_beef",
    "chicken": "food-type_chicken",
    "bacon_frying_raw": "food-type_bacon_frying_raw",

    # DAIRY
    "blue_cheese": "food-type_blue_cheese",
    "butter_salt_added": "food-type_butter_salt_added",
    "almond_milk_unfortified": "food-type_almond_milk_unfortified",

    # SEAFOOD
    "cod_fillet_raw": "food-type_cod_fillet_raw",
    "crab_boiled": "food-type_crab_boiled",

    # OTHER
    "egg_chicken_free_range_hens_indoor_raw": "food-type_eggs_chicken_free_range_hens_indoor_raw",
}

EMISSION_CATEGORIES = [
    "total",  # Often the most useful
    "agriculture",
    "transport",
    "processing",
    "packaging",
    "retail",
    "land_use_change",
]


class CarbonRecipeGUI:
    def __init__(self, master):
        self.master = master
        master.title("🌱 Recipe Carbon Footprint Calculator")

        # Dictionary to hold the current recipe: {food_name: (weight_kg, category)}
        self.current_recipe = {}
        self.total_co2e = 0.0

        # --- Frames ---
        # Main structure uses a grid layout with frames for organisation
        self.list_frame = tk.Frame(master)
        self.list_frame.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')

        self.recipe_frame = tk.Frame(master)
        self.recipe_frame.grid(row=0, column=1, padx=10, pady=10, sticky='nsew')

        # --- 1. Available Ingredients Listbox (Left Side) ---
        tk.Label(self.list_frame, text="Available Ingredients (select one):").pack(side=tk.TOP, pady=5)

        self.available_listbox = tk.Listbox(self.list_frame, selectmode=tk.SINGLE, height=15, width=35)
        self.available_listbox.pack(side=tk.LEFT, fill=tk.Y)

        self.avail_scrollbar = tk.Scrollbar(self.list_frame, orient=tk.VERTICAL, command=self.available_listbox.yview)
        self.available_listbox.config(yscrollcommand=self.avail_scrollbar.set)
        self.avail_scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        # Populate Available Listbox
        for item in FOOD_EMISSION_FACTORS.keys():
            self.available_listbox.insert(tk.END, item)

        # --- 2. Action/Category Selection (Center) ---
        self.action_frame = tk.Frame(master)
        self.action_frame.grid(row=1, column=0, columnspan=2, pady=5)

        self.add_button = tk.Button(self.action_frame, text="Add Item to Recipe", command=self.prompt_for_details)
        self.add_button.pack(side=tk.LEFT, padx=5)

        self.remove_button = tk.Button(self.action_frame, text="Remove Selected Item", command=self.remove_from_recipe)
        self.remove_button.pack(side=tk.LEFT, padx=5)

        # Category dropdown setup
        tk.Label(self.action_frame, text="Emission Category:").pack(side=tk.LEFT, padx=10)
        self.category_var = tk.StringVar(master)
        self.category_var.set(EMISSION_CATEGORIES[0])  # Default value: total
        self.category_menu = tk.OptionMenu(self.action_frame, self.category_var, *EMISSION_CATEGORIES)
        self.category_menu.pack(side=tk.LEFT, padx=5)

        # --- 3. Current Recipe Listbox (Right Side) ---
        tk.Label(self.recipe_frame, text="Current Recipe:").pack(side=tk.TOP, pady=5)

        self.recipe_listbox = tk.Listbox(self.recipe_frame, selectmode=tk.SINGLE, height=15, width=50)
        self.recipe_listbox.pack(side=tk.LEFT, fill=tk.Y)

        self.recipe_scrollbar = tk.Scrollbar(self.recipe_frame, orient=tk.VERTICAL, command=self.recipe_listbox.yview)
        self.recipe_listbox.config(yscrollcommand=self.recipe_scrollbar.set)
        self.recipe_scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        # --- 4. Calculate Button and Result ---
        self.calculate_button = tk.Button(master, text="Calculate Total CO2e", command=self.start_calculation)
        self.calculate_button.grid(row=2, column=0, columnspan=2, padx=10, pady=10)

        self.result_label = tk.Label(master, text="Total CO2e: 0.00 kg CO2e", font=('Arial', 14, 'bold'), fg='darkblue')
        self.result_label.grid(row=3, column=0, columnspan=2, padx=10, pady=10)

        # Configure resizing
        master.grid_columnconfigure(0, weight=1)
        master.grid_columnconfigure(1, weight=1)
        master.grid_rowconfigure(0, weight=1)

    def prompt_for_details(self):
        """Prompts for weight and adds the selected item to the recipe."""
        selected_index = self.available_listbox.curselection()

        if not selected_index:
            messagebox.showinfo("Selection Error", "Please select an ingredient to add from the left list.")
            return

        food_name = self.available_listbox.get(selected_index[0])
        category = self.category_var.get()

        try:
            weight = simpledialog.askfloat(
                "Weight Input",
                f"Enter weight of '{food_name}' in kilograms (kg):",
                initialvalue=0.1,
                minvalue=0.001
            )
        except Exception:
            # Handle case where dialog is cancelled or invalid input
            return

        if weight is not None:
            # Store food name as key, and (weight, category) as value
            self.current_recipe[food_name] = (weight, category)
            self.update_recipe_listbox()

    def remove_from_recipe(self):
        """Removes the selected item from the current recipe."""
        selected_index = self.recipe_listbox.curselection()

        if not selected_index:
            messagebox.showinfo("Selection Error", "Please select an item to remove from the recipe list.")
            return

        # Get the full listbox text to determine the food name
        full_text = self.recipe_listbox.get(selected_index[0])
        # The food name is everything before the first space
        food_name = full_text.split(" ")[0].strip()

        if food_name in self.current_recipe:
            del self.current_recipe[food_name]
            self.update_recipe_listbox()
            self.result_label.config(text="Total CO2e: 0.00 kg CO2e")  # Reset cost display

    def update_recipe_listbox(self):
        """Clears and repopulates the recipe listbox based on self.current_recipe."""
        self.recipe_listbox.delete(0, tk.END)
        for food, (weight, category) in self.current_recipe.items():
            line = f"{food} ({category}): {weight:.3f} kg"
            self.recipe_listbox.insert(tk.END, line)

    def start_calculation(self):
        """Starts the API call in a separate thread to prevent GUI freezing."""
        if not self.current_recipe:
            messagebox.showinfo("Recipe Empty", "The current recipe is empty. Add ingredients first.")
            return

        self.calculate_button.config(text="Calculating...", state=tk.DISABLED)
        self.result_label.config(text="Sending API Requests...")

        # Run the calculation in a thread so the GUI doesn't freeze
        thread = threading.Thread(target=self.perform_api_calculation)
        thread.start()

    def perform_api_calculation(self):
        """
        Calculates the total CO2e by making API calls for each recipe item.
        Runs in a separate thread.
        """
        total_co2e = 0.0
        successful_requests = 0

        # Iterate over a copy to ensure safe threading
        for food_name, (weight_kg, category) in list(self.current_recipe.items()):

            # The API expects weight in tonnes, so convert kilograms to tonnes (1 kg = 0.001 t)
            weight_kilograms = weight_kg / 1000.0
            activity_id = FOOD_EMISSION_FACTORS.get(food_name)

            # --- Build and Send API Request ---
            data = {
                "emission_factor": {
                    "activity_id": activity_id,
                    "source": "CONCITO and 2-0 LCA",
                    "region": "GB",
                    "year": 2024,
                    "source_lca_activity": category,
                    "data_version": "^27"
                },
                "parameters": {
                    "weight": weight_kilograms,
                    "weight_unit": "t"
                }
            }

            try:
                response = requests.post(API_URL, headers=API_HEADERS, json=data, timeout=10)
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

                result = response.json()
                co2e_kg = result.get("co2e", 0)  # API returns CO2e in kg by default
                total_co2e += co2e_kg
                successful_requests += 1

            except requests.exceptions.RequestException as e:
                # Update GUI with error message and stop calculation
                error_msg = f"API Error for {food_name}: {e}"
                print(error_msg)
                self.master.after(0, lambda: self.reset_button(error_msg))
                return

        # Update GUI elements after the loop finishes (must use .after(0, ...))
        final_message = f"Total CO2e for {successful_requests} items: {total_co2e:.3f} kg"
        self.master.after(0, lambda: self.display_final_result(total_co2e, final_message))

    def display_final_result(self, total_co2e, message):
        """Updates the GUI with the final result."""
        self.total_co2e = total_co2e
        self.result_label.config(text=f"Total CO2e: {total_co2e:.3f} kg CO2e")
        self.calculate_button.config(text="Calculate Total CO2e", state=tk.NORMAL)
        messagebox.showinfo("Calculation Complete", message)

    def reset_button(self, error_message):
        """Resets the button state after an error."""
        self.result_label.config(text=f"Error: {error_message[:40]}...")
        self.calculate_button.config(text="Calculate Total CO2e (Error)", state=tk.NORMAL)


# --- Main execution block ---
if __name__ == "__main__":
    root = tk.Tk()
    app = CarbonRecipeGUI(root)
    root.mainloop()