import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import json
import os


class FoodTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EcoPantry - Food Waste Tracker")
        self.root.geometry("800x650")

        # Color Palette
        self.bg_color = "#f0f0f0"
        self.primary_color = "#4CAF50"  # Green
        self.warning_color = "#FF9800"  # Orange
        self.alert_color = "#F44336"  # Red

        self.root.configure(bg=self.bg_color)

        # Files
        self.pantry_file = "json files/pantry_data.json"
        self.gui_db_file = "json files/gui_ingredients.json"

        # Load Data
        self.food_items = self.load_pantry_data()
        self.master_ingredient_dict = self.load_gui_database()

        # Build the visually tagged dropdown list
        raw_options = []
        for name, has_co2 in self.master_ingredient_dict.items():
            display_name = name.title()
            if has_co2:
                display_name += " 🌱"
            raw_options.append(display_name)

        # --- NEW: Sort the list so CO2 (🌱) items are ALWAYS at the top ---
        # The tuple (not " 🌱" in x, x) sorts by presence of leaf first (True/False math), then alphabetically
        self.db_options = sorted(raw_options, key=lambda x: (" 🌱" not in x, x))

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

    def load_gui_database(self):
        if not os.path.exists(self.gui_db_file):
            print(f"Warning: {self.gui_db_file} not found. Run the prep script first.")
            return {}
        try:
            with open(self.gui_db_file, 'r') as f:
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

        legend_lbl = tk.Label(input_frame, text="🌱 = Carbon Tracked Ingredient", bg=self.bg_color,
                              fg=self.primary_color, font=("Arial", 9, "bold"))
        legend_lbl.grid(row=0, column=0, columnspan=5, pady=(0, 10), sticky="w")

        tk.Label(input_frame, text="Food Item:", bg=self.bg_color).grid(row=1, column=0, padx=5, sticky="e")

        # 1. Use a standard Entry instead of Combobox
        self.name_entry = tk.Entry(input_frame, width=30)
        self.name_entry.grid(row=1, column=1, padx=5, sticky="n")

        # 2. Create the Listbox directly below it
        self.suggestion_list = tk.Listbox(input_frame, height=5, width=30)
        self.suggestion_list.grid(row=2, column=1, padx=5, sticky="n")

        # Hide the listbox initially
        self.suggestion_list.grid_remove()

        # 3. Bindings
        self.name_entry.bind('<KeyRelease>', self.update_suggestions)
        self.name_entry.bind('<Return>', lambda event: self.add_item())
        self.suggestion_list.bind('<<ListboxSelect>>', self.select_suggestion)

        tk.Label(input_frame, text="Expiry Date (YYYY-MM-DD):", bg=self.bg_color).grid(row=1, column=2, padx=5,
                                                                                       sticky="ne")
        self.date_entry = tk.Entry(input_frame, width=15)
        self.date_entry.grid(row=1, column=3, padx=5, sticky="n")
        self.date_entry.insert(0, datetime.date.today().strftime("%Y-%m-%d"))

        add_btn = tk.Button(input_frame, text="Add to Pantry", command=self.add_item,
                            bg=self.primary_color, fg="white", font=("Arial", 10, "bold"), padx=10)
        add_btn.grid(row=1, column=4, padx=15, sticky="n")

    def update_suggestions(self, event):
        # Ignore navigation keys
        if event.keysym in ('Up', 'Down', 'Return', 'Tab'):
            return

        typed_text = self.name_entry.get().lower()
        self.suggestion_list.delete(0, tk.END)  # Clear current list

        if typed_text == "":
            self.suggestion_list.grid_remove()  # Hide if empty
            return

        # Filter options
        filtered = [opt for opt in self.db_options if typed_text in opt.lower()]

        if filtered:
            self.suggestion_list.grid()  # Show list
            for item in filtered[:10]:  # Only show top 10 results to keep UI clean
                self.suggestion_list.insert(tk.END, item)
        else:
            self.suggestion_list.grid_remove()

    def select_suggestion(self, event):
        # When user clicks an item in the listbox, put it in the entry box
        if not self.suggestion_list.curselection():
            return

        selected = self.suggestion_list.get(self.suggestion_list.curselection())

        self.name_entry.delete(0, tk.END)
        self.name_entry.insert(0, selected)
        self.suggestion_list.grid_remove()  # Hide list after selection
        self.name_entry.focus_set()  # Return cursor to entry box


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
        raw_selection = self.name_entry.get().strip()
        date_str = self.date_entry.get().strip()

        if not raw_selection or not date_str:
            messagebox.showerror("Error", "Please select an item and enter a date.")
            return

        try:
            datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Error", "Invalid Date Format. Please use YYYY-MM-DD.")
            return

        clean_name = raw_selection.replace(" 🌱", "").lower()

        new_item = {
            "name": clean_name,
            "display_name": raw_selection,
            "date": date_str
        }

        self.food_items.append(new_item)
        self.save_data()
        self.refresh_list()
        self.suggestion_list.grid_remove()
        self.name_entry.set('')

        # Reset the combobox list to the full list after adding
        self.name_entry['values'] = self.db_options

    def delete_item(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select an item to remove.")
            return

        for item in selected_item:
            values = self.tree.item(item, "values")
            display_name_to_remove = values[0]
            date_to_remove = values[1]

            self.food_items = [
                f for f in self.food_items
                if not (f.get('display_name', f['name']) == display_name_to_remove and f['date'] == date_to_remove)
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

                display = item.get('display_name', item['name'].title())

                self.tree.insert("", "end", values=(display, item['date'], f"{delta} days", status), tags=(tag,))
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
        os.makedirs(os.path.dirname(self.pantry_file), exist_ok=True)
        with open(self.pantry_file, 'w') as f:
            json.dump(self.food_items, f, indent=4)


if __name__ == "__main__":
    root = tk.Tk()
    app = FoodTrackerApp(root)
    root.mainloop()