import gensim
import pandas as pd

# Load your model
w2v_model = gensim.models.Word2Vec.load("Data/archive/ingredient_w2v.model")


def evaluate_word2vec_swaps(model):
    # (Target Ingredient, Known Good Swap, Known Bad Swap)
    test_cases = [
        # --- DOMAIN 1: PROTEINS & MEATS ---
        ("beef", "pork", "apple"),
        ("chicken", "turkey", "banana"),
        ("salmon", "trout", "cheese"),
        ("shrimp", "prawns", "flour"),
        ("lamb", "mutton", "sugar"),
        ("bacon", "pancetta", "strawberry"),
        ("tofu", "tempeh", "beef"),
        ("sausage", "chorizo", "milk"),
        ("ham", "prosciutto", "chocolate"),
        ("tuna", "mackerel", "vanilla"),
        ("bacon", "ham", "honey"),

        # --- DOMAIN 2: VEGETABLES & PRODUCE ---
        ("potato", "sweet potato", "chicken"),
        ("spinach", "kale", "milk"),
        ("onion", "shallot", "sugar"),
        ("broccoli", "cauliflower", "flour"),
        ("carrot", "parsnip", "chocolate"),
        ("tomatoes", "tomatillo", "oats"),
        ("cabbage", "lettuce", "butter"),
        ("zucchini", "courgette", "pork"),
        ("mushroom", "eggplant", "cinnamon"),
        ("garlic", "ginger", "marshmallows"),
        ("apple", "pear", "beef"),
        ("lemon", "lime", "chicken"),
        ("orange", "tangerine", "garlic"),
        ("strawberries", "raspberries", "onion"),
        ("peach", "nectarine", "pork"),
        ("blueberries", "blackberry", "salt"),

        # --- DOMAIN 3: DAIRY & FATS ---
        ("butter", "margarine", "garlic"),
        ("milk", "cream", "spinach"),
        ("cheddar", "mozzarella", "carrot"),
        ("parmesan", "pecorino", "apple"),
        ("yogurt", "sour cream", "beef"),
        ("oil", "shortening", "sugar"),
        ("mayonnaise", "mustard", "strawberries"),
        ("brie", "camembert", "onion"),
        ("ghee", "butter", "lettuce"),
        ("buttermilk", "kefir", "pork"),

        # --- DOMAIN 4: CARBOHYDRATES & GRAINS ---
        ("rice", "quinoa", "beef"),  # The known complement-failure case
        ("pasta", "noodles", "strawberries"),
        ("bread", "toast", "chicken"),
        ("flour", "cornstarch", "pork"),
        ("oats", "barley", "tomatoes"),
        ("couscous", "bulgur", "apple"),
        ("tortilla", "wrap", "milk"),

        # --- DOMAIN 5: BAKING, SPICES & PANTRY ---
        ("sugar", "honey", "onion"),
        ("chocolate", "cocoa", "garlic"),
        ("vanilla", "almonds", "beef"),
        ("syrup", "agave", "salt"),
        ("basil", "oregano", "sugar"),
        ("cilantro", "parsley", "chocolate"),
        ("cinnamon", "nutmeg", "pork"),
        ("cumin", "coriander", "apple"),
        ("thyme", "rosemary", "honey"),
        ("vinegar", "lemon", "beef")
    ]

    results = []

    for target, good, bad in test_cases:
        try:
            # Calculate Cosine Similarity (1.0 is identical, 0.0 is completely unrelated)
            good_score = model.wv.similarity(target, good)
            bad_score = model.wv.similarity(target, bad)

            # Did the AI correctly rank the good swap higher than the bad one?
            success = "Pass" if good_score > bad_score else "Fail"

            results.append({
                "Target Ingredient": target.title(),
                "Good Swap": good.title(),
                "Similarity (Good)": round(good_score, 3),
                "Bad Swap": bad.title(),
                "Similarity (Bad)": round(bad_score, 3),
                "Result": success
            })
        except KeyError as e:
            print(f"Skipping {target} - Word not in vocabulary: {e}")

    df_results = pd.DataFrame(results)
    return df_results


# Run and save to CSV so you can put it in your dissertation!
w2v_results = evaluate_word2vec_swaps(w2v_model)
print(w2v_results)
w2v_results.to_csv("word2vec_evaluation.csv", index=False)