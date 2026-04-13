import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import json
import os


class FoodTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EcoPantry - Food Waste Tracker")
        self.root.geometry("800x600")

        # Color Palette
        self.bg_color = "#f0f0f0"
        self.primary_color = "#4CAF50"  # Green
        self.warning_color = "#FF9800"  # Orange
        self.alert_color = "#F44336"  # Red

        self.root.configure(bg=self.bg_color)

        # Files
        self.pantry_file = "json files/pantry_data.json"
        self.db_file = "json files/food_database_complete.json"  # The new database file

        # Load Data
        self.food_items = self.load_pantry_data()
        self.food_database = self.load_food_database()

        # Create a list of readable names for the dropdown
        # Converts "apple_juice" -> "Apple Juice"
        self.db_options = sorted([k.replace('_', ' ').title() for k in self.food_database.keys()])

        # Styles
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Treeview", rowheight=25, font=("Arial", 11))
        self.style.configure("Treeview.Heading", font=("Arial", 12, "bold"))

        # GUI Setup
        self.create_header()
        self.create_input_section()
        self.create_list_section()
        self.create_footer()

        # Initial data load
        self.refresh_list()

    def load_food_database(self):
        """Loads the static reference database for ingredients"""
        if not os.path.exists(self.db_file):
            # If file doesn't exist, return empty dict or create a dummy one for testing
            print(f"Warning: {self.db_file} not found.")
            return {}
        try:
            with open(self.db_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load food database: {e}")
            return {}

    def create_header(self):
        header_frame = tk.Frame(self.root, bg=self.primary_color, pady=10)
        header_frame.pack(fill="x")

        title_label = tk.Label(header_frame, text="EcoPantry: Smart Food Tracker",
                               font=("Helvetica", 18, "bold"), bg=self.primary_color, fg="white")
        title_label.pack()

        subtitle_label = tk.Label(header_frame, text="Track expiration dates to reduce waste",
                                  font=("Helvetica", 10), bg=self.primary_color, fg="#e8f5e9")
        subtitle_label.pack()

    def create_input_section(self):
        input_frame = tk.LabelFrame(self.root, text="Add New Item", bg=self.bg_color, font=("Arial", 10, "bold"),
                                    pady=10, padx=10)
        input_frame.pack(fill="x", padx=20, pady=10)

        # --- MODIFIED SECTION: COMBOBOX INSTEAD OF ENTRY ---
        tk.Label(input_frame, text="Food Item:", bg=self.bg_color).grid(row=0, column=0, padx=5, sticky="e")

        # Using Combobox for selection
        self.name_entry = ttk.Combobox(input_frame, width=23, values=self.db_options)
        self.name_entry.grid(row=0, column=1, padx=5)
        self.name_entry.bind('<Return>', lambda event: self.add_item())  # Allow hitting Enter to add

        # Date Entry
        tk.Label(input_frame, text="Expiry Date (YYYY-MM-DD):", bg=self.bg_color).grid(row=0, column=2, padx=5,
                                                                                       sticky="e")
        self.date_entry = tk.Entry(input_frame, width=15)
        self.date_entry.grid(row=0, column=3, padx=5)
        self.date_entry.insert(0, datetime.date.today().strftime("%Y-%m-%d"))

        # Add Button
        add_btn = tk.Button(input_frame, text="Add to Pantry", command=self.add_item,
                            bg=self.primary_color, fg="white", font=("Arial", 10, "bold"), padx=10)
        add_btn.grid(row=0, column=4, padx=15)

    def create_list_section(self):
        list_frame = tk.Frame(self.root, bg=self.bg_color)
        list_frame.pack(fill="both", expand=True, padx=20, pady=5)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        columns = ("name", "date", "days_left", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", yscrollcommand=scrollbar.set)

        self.tree.heading("name", text="Food Item")
        self.tree.heading("date", text="Expiry Date")
        self.tree.heading("days_left", text="Days Remaining")
        self.tree.heading("status", text="Status")

        self.tree.column("name", width=200)
        self.tree.column("date", width=100, anchor="center")
        self.tree.column("days_left", width=100, anchor="center")
        self.tree.column("status", width=150, anchor="center")

        self.tree.tag_configure("expired", background="#ffcccc", foreground="black")
        self.tree.tag_configure("urgent", background="#fff3cd", foreground="black")
        self.tree.tag_configure("fresh", background="white", foreground="black")

        self.tree.pack(fill="both", expand=True)
        scrollbar.config(command=self.tree.yview)

    def create_footer(self):
        footer_frame = tk.Frame(self.root, bg=self.bg_color, pady=10)
        footer_frame.pack(fill="x", padx=20)

        delete_btn = tk.Button(footer_frame, text="Remove Selected Item", command=self.delete_item,
                               bg="#d32f2f", fg="white", font=("Arial", 10))
        delete_btn.pack(side="right")

        ai_btn = tk.Button(footer_frame, text="Generate Recipe (AI Pending)", state="disabled",
                           bg="#2196F3", fg="white", font=("Arial", 10))
        ai_btn.pack(side="left")

    def add_item(self):
        name = self.name_entry.get().strip()
        date_str = self.date_entry.get().strip()

        if not name or not date_str:
            messagebox.showerror("Error", "Please select an item and enter a date.")
            return

        try:
            # Validate date format
            datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Error", "Invalid Date Format. Please use YYYY-MM-DD.")
            return

        # Optional: Retrieve extra data from DB if it exists (e.g., calories)
        # We reconvert readable name "Apple Juice" back to potential keys or just store as is.
        # For now, we simply store the readable name the user selected.

        new_item = {
            "name": name,
            "date": date_str
        }

        self.food_items.append(new_item)
        self.save_data()
        self.refresh_list()

        # Clear inputs
        self.name_entry.set('')  # Clear combobox

    def delete_item(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select an item to remove.")
            return

        for item in selected_item:
            values = self.tree.item(item, "values")
            name_to_remove = values[0]
            date_to_remove = values[1]

            self.food_items = [
                f for f in self.food_items
                if not (f['name'] == name_to_remove and f['date'] == date_to_remove)
            ]

        self.save_data()
        self.refresh_list()

    def refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        today = datetime.date.today()
        self.food_items.sort(key=lambda x: x['date'])

        for item in self.food_items:
            try:
                exp_date = datetime.datetime.strptime(item['date'], "%Y-%m-%d").date()
                delta = (exp_date - today).days

                status = ""
                tag = "fresh"

                if delta < 0:
                    status = "EXPIRED"
                    tag = "expired"
                elif delta == 0:
                    status = "Expires Today!"
                    tag = "urgent"
                elif delta <= 3:
                    status = "Use Soon"
                    tag = "urgent"
                else:
                    status = "Good"
                    tag = "fresh"

                self.tree.insert("", "end", values=(item['name'], item['date'], f"{delta} days", status), tags=(tag,))
            except ValueError:
                continue

    def load_pantry_data(self):
        if not os.path.exists(self.pantry_file):
            return []
        try:
            with open(self.pantry_file, 'r') as f:
                return json.load(f)
        except:
            return []

    def save_data(self):
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.pantry_file), exist_ok=True)
        with open(self.pantry_file, 'w') as f:
            json.dump(self.food_items, f, indent=4)


if __name__ == "__main__":
    # Create a dummy database file for testing if it doesn't exist
    if not os.path.exists("json files/food_database_repaired.json"):
        os.makedirs("json files", exist_ok=True)
        dummy_db = {
            "apple_juice_canned_or_bottled": {"kcal_per_kg": 460, "category": "Fruit"},
            "banana": {"kcal_per_kg": 890, "category": "Fruit"},
            "cheddar_cheese": {"kcal_per_kg": 4020, "category": "Dairy"},
            "milk_whole": {"kcal_per_kg": 600, "category": "Dairy"},
            "bread_whole_wheat": {"kcal_per_kg": 2500, "category": "Grain"}
        }
        with open("json files/food_db.json", "w") as f:
            json.dump(dummy_db, f, indent=4)
        print("Created dummy 'food_db.json' for testing.")

    root = tk.Tk()
    app = FoodTrackerApp(root)
    root.mainloop()