# SustainaBite 🌱
**AI-Driven Food Intelligence & Carbon Mitigation Platform**

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Machine Learning](https://img.shields.io/badge/Machine%20Learning-Word2Vec%20%7C%20XGBoost-orange)
![Frontend](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B)
![Status](https://img.shields.io/badge/Status-Prototype%20%2F%20Research-success)

SustainaBite is an automated, multi-objective meal planning and household inventory management system. Developed as a Master's research project, this platform mitigates domestic food waste (and its associated Scope 3 greenhouse gas emissions) by algorithmically routing users toward low-carbon dietary paths and dynamically exhausting expiring pantry inventory. 

## 📖 Project Overview
In the UK, households generate approximately 6.0 million tonnes of food waste annually, 73% of which is classified as "avoidable." SustainaBite acts as a digital intervention tool, solving the domestic "supply knowledge" gap via two computational phases:
1. **Source Reduction (Upstream):** Utilising NLP and Machine Learning to generate zero-waste, carbon-optimised meal plans that prevent the embodied emissions of purchasing replacement food.
2. **End-of-Life Diversion (Downstream):** A gamified educational UI that tracks methane ($CH_4$) mitigation through aerobic composting, utilising the **IPCC 2019 First Order Decay (FOD)** methodology.

## ✨ Core Features & Architecture

### 🧠 1. Semantic Ingredient Substitution (Word2Vec)
To bypass the limitations of rigid relational databases, the engine utilises unsupervised NLP to map the semantic context of 14,000+ ingredients. 
* Trained a **TF-IDF weighted Word2Vec model** to generate a 100-dimensional vector space.
* Implements a **Smart Substitution Engine** that uses cosine similarity to suggest highly accurate, context-aware ingredient swaps (e.g., substituting missing butter with available margarine).
* Features a **Human-in-the-Loop (HITL)** UI checkbox to mitigate algorithmic hallucinations and grant the user culinary autonomy.

### 📈 2. Predictive Quality Imputation (XGBoost)
Crowdsourced recipe databases inherently suffer from missing data and extreme "politeness bias" (where the vast majority of recipes are rated 4 or 5 stars).
* Engineered an **XGBoost Regressor** to impute missing 0-star ratings by synthesizing NLP word embeddings with tabular nutritional metadata.
* Solves the "Cold-Start Problem," achieving a **Mean Absolute Error (MAE) of 0.44** on a dataset of 180,000+ recipes.

### 🌍 3. Low-Carbon Routing & Constraint Satisfaction
The core algorithmic generation engine evaluates meal planning as a **Constraint Satisfaction Problem (CSP)**.
* Applies binary pre-filtering (dietary tags, prep time) to drastically reduce the backend search space.
* Scores thousands of recipes using a custom matrix that weighs the **time-decay of expiring inventory** against the **marginal procurement carbon score** ($CO_2e$) derived from Life Cycle Assessment (LCA) databases.
* Sub-7-second generation latency achieved via state persistence caching and pure Python dictionary migration.

## 📊 Empirical Results & Theoretical Impact
Based on rigorous system evaluation and modeling against national WRAP baselines, the SustainaBite architecture achieves:
* **96% Algorithmic Accuracy** in semantic ingredient substitution mapping.
* **< 7.0s Execution Latency** for a fully optimized 21-meal weekly plan.
* **Theoretical Environmental Impact:** Projected to prevent **46 kg of upstream food waste** and mitigate **321.4 kg of downstream $CO_2e$ emissions** per UK household, annually.

## 🛠️ Tech Stack
* **Backend Engine:** Python, Pandas, NumPy
* **Machine Learning:** Gensim (Word2Vec), XGBoost, Scikit-Learn
* **Frontend UI:** Streamlit
* **Data Sources:** Food.com Recipe Corpus (180k+ rows), Climatiq API (Carbon LCA factors)

## 🔮 Future Developments
* **Agentic LLM Workflows:** Integration of a 'Critic Agent' to pragmatically evaluate recipe viability (e.g., filtering out structural components like "pizza dough" tagged as main meals).

* **Computer Vision (OCR/CNNs):** Frictionless inventory acquisition via grocery receipt scanning and smart-fridge image recognition.

* **Longitudinal Gamification:** Deployment of social benchmarking and achievement badges to secure long-term behavioral change.

## 🚀 Installation & Local Deployment

*Note: Due to GitHub file size constraints, the raw 600MB+ datasets (`RAW_recipes.xlsx`), trained models (`.model`), and cached dataframes (`.pkl`) are excluded via `.gitignore`. The code is provided for architectural review.*

```bash
# 1. Clone the repository
git clone [https://github.com/TobyCalvert/SustainaBite.git](https://github.com/TobyCalvert/SustainaBite.git)

# 2. Navigate to the project directory
cd SustainaBite

# 3. Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the Streamlit application
streamlit run app.py

```
---
**Developed by Toby Calvert | Supervised by Raheleh Kafieh**
