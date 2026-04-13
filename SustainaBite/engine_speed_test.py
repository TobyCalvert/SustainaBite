import time
import numpy as np
# Import your actual function from your backend file
from RF_calcsV3 import generate_meal_plan


def benchmark_engine_speed(iterations=50):
    # A dummy pantry for the engine to process
    dummy_pantry = [
    {
        "name": "water",
        "display_name": "Water",
        "date": "2026-03-12",
        "quantity": 1,
        "is_infinite": True
    },
    {
        "name": "salt",
        "display_name": "Salt",
        "date": "N/A",
        "quantity": 1,
        "is_infinite": True
    },
    {
        "name": "black pepper",
        "display_name": "Black Pepper \ud83c\udf31",
        "date": "N/A",
        "quantity": 1,
        "is_infinite": True
    },
    {
        "name": "oil olive",
        "display_name": "Oil Olive \ud83c\udf31",
        "date": "N/A",
        "quantity": 1,
        "is_infinite": True
    },
    {
        "name": "onion",
        "display_name": "Onion \ud83c\udf31",
        "date": "2026-04-09",
        "quantity": 2,
        "is_infinite": False
    },
    {
        "name": "pasta",
        "display_name": "Pasta \ud83c\udf31",
        "date": "2026-04-09",
        "quantity": 2,
        "is_infinite": False
    },
    {
        "name": "butter",
        "display_name": "Butter",
        "date": "2026-04-16",
        "quantity": 5,
        "is_infinite": False
    },
    {
        "name": "flour",
        "display_name": "Flour",
        "date": "2026-07-30",
        "quantity": 10,
        "is_infinite": False
    },
    {
        "name": "milk",
        "display_name": "Milk",
        "date": "2026-04-24",
        "quantity": 5,
        "is_infinite": False
    },
    {
        "name": "egg",
        "display_name": "Egg",
        "date": "2026-04-17",
        "quantity": 6,
        "is_infinite": False
    },
    {
        "name": "chicken",
        "display_name": "Chicken \ud83c\udf31",
        "date": "2026-04-10",
        "quantity": 3,
        "is_infinite": False
    },
    {
        "name": "bacon",
        "display_name": "Bacon \ud83c\udf31",
        "date": "2026-04-06",
        "quantity": 4,
        "is_infinite": False
    },
    {
        "name": "banana",
        "display_name": "Banana \ud83c\udf31",
        "date": "2026-04-02",
        "quantity": 2,
        "is_infinite": False
    }
]

    execution_times = []
    print(f"Benchmarking meal plan generation over {iterations} iterations...")

    for i in range(iterations):
        start_time = time.time()

        # Run the engine silently
        _ = generate_meal_plan(pantry_data=dummy_pantry, min_rating=4.0, days=7)

        end_time = time.time()
        execution_times.append(end_time - start_time)

    avg_time = np.mean(execution_times)
    std_time = np.std(execution_times)
    max_time = np.max(execution_times)

    print("\n--- PERFORMANCE RESULTS ---")
    print(f"Average Execution Time: {avg_time:.3f} seconds")
    print(f"Standard Deviation: {std_time:.3f} seconds")
    print(f"Worst-Case Execution Time: {max_time:.3f} seconds")


# Run the benchmark
benchmark_engine_speed()