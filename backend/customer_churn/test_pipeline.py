import os
import pandas as pd
import numpy as np
import joblib

# Import local pipeline classes
from dataset.generate_mock_data import generate_mock_churn_data
from preprocess import ChurnPreprocessor
from model import train_and_evaluate_models

def run_pipeline_test():
    print("=== STARTING CHURN PREDICTION PIPELINE VALIDATION ===")

    # 1. Generate Mock Data
    csv_path = "dataset/sample_churn.csv"
    if not os.path.exists(csv_path):
        print("Generating mock customer churn dataset...")
        generate_mock_churn_data(csv_path, num_samples=500)
    else:
        print("Mock dataset already exists.")

    # Verify file
    df = pd.read_csv(csv_path)
    print(f"Dataset shape: {df.shape}")
    assert df.shape[0] >= 500, "Dataset has fewer rows than expected"

    # 2. Run Preprocessing
    print("\nRunning preprocessor...")
    preprocessor = ChurnPreprocessor()
    X_trans, y = preprocessor.fit_transform(df, target_col="Churn")

    print(f"Preprocessed features shape: {X_trans.shape}")
    print(f"Target vector shape: {y.shape}")
    print(f"Detected columns: ID = {preprocessor.id_col}, Target = {preprocessor.target_col}")
    print(f"Numerical columns count: {len(preprocessor.num_cols)}")
    print(f"Categorical columns count: {len(preprocessor.cat_cols)}")

    # Save preprocessor
    prep_path = "models/preprocessor.joblib"
    preprocessor.save(prep_path)
    assert os.path.exists(prep_path), "Preprocessor joblib not created"

    # 3. Train Models
    print("\nRunning model training and evaluation...")
    evaluation, best_model_path = train_and_evaluate_models(
        X_trans, y, preprocessor.feature_cols
    )

    print("\nModel Training Comparison Leaderboard:")
    for name, metrics in evaluation["models_comparison"].items():
        print(f"- {name}:")
        print(f"  Accuracy  : {metrics['Accuracy']:.4f}")
        print(f"  Precision : {metrics['Precision']:.4f}")
        print(f"  Recall    : {metrics['Recall']:.4f}")
        print(f"  F1 Score  : {metrics['F1 Score']:.4f}")
        print(f"  ROC-AUC   : {metrics['ROC-AUC']:.4f}")

    print(f"\nBest Model Selected: {evaluation['best_model_name']}")
    assert os.path.exists(best_model_path), "Best model joblib not created"

    # 4. Save Correlation Weights
    print("\nGenerating feature correlations with Churn target...")
    feature_correlations = {}
    for col in preprocessor.feature_cols:
        feat_values = X_trans[col].values
        corr = np.corrcoef(feat_values, y)[0, 1]
        if np.isnan(corr):
            corr = 0.0
        feature_correlations[col] = float(corr)

    # Reload and save preprocessor with correlation info
    prep_state = joblib.load(prep_path)
    prep_state["feature_correlations"] = feature_correlations
    joblib.dump(prep_state, prep_path)

    # 5. Run Single Customer Test Prediction (High-Risk Profile)
    print("\nEvaluating test customer churn prediction...")
    test_customer = {
        "customerID": "TEST-9988",
        "gender": "Female",
        "SeniorCitizen": 1,
        "Partner": "No",
        "Dependents": "No",
        "tenure": 2,                      # Short tenure (High risk)
        "PhoneService": "Yes",
        "MultipleLines": "Yes",
        "InternetService": "Fiber optic",  # Fiber optic (High risk)
        "OnlineSecurity": "No",           # No security (High risk)
        "OnlineBackup": "No",
        "DeviceProtection": "No",
        "TechSupport": "No",              # No support (High risk)
        "StreamingTV": "Yes",
        "StreamingMovies": "Yes",
        "Contract": "Month-to-month",      # Month-to-month (High risk)
        "PaperlessBilling": "Yes",
        "PaymentMethod": "Electronic check", # Electronic check (High risk)
        "MonthlyCharges": 95.80,          # High monthly billing (High risk)
        "TotalCharges": 191.60
    }

    df_single = pd.DataFrame([test_customer])

    # Load pipeline
    loaded_prep = ChurnPreprocessor.load(prep_path)
    loaded_model = joblib.load(best_model_path)

    # Transform
    X_single_trans = loaded_prep.transform(df_single)

    # Predict probability
    prob = float(loaded_model.predict_proba(X_single_trans)[0][1])
    pred = "Churn" if prob >= 0.5 else "Stay"
    print(f"Test Customer Churn Prediction: {pred} (Probability: {prob*100:.1f}%)")

    # Check XAI
    print("\nEvaluating XAI feature contributions...")
    # Retrieve preprocessor state correlations
    preprocessor_state = joblib.load(prep_path)
    correlations = preprocessor_state.get("feature_correlations", {})

    # Get global feature importances
    global_importances = evaluation["feature_importance"]
    importances_dict = {item["feature"]: item["importance"] for item in global_importances}

    local_contribs = []
    is_lr = hasattr(loaded_model, "coef_")
    if is_lr:
        coefs = loaded_model.coef_[0]
        for idx, col in enumerate(loaded_prep.feature_cols):
            val_trans = X_single_trans[col].values[0]
            contrib = float(coefs[idx] * val_trans)
            local_contribs.append({"feature": col, "contribution": contrib})
    else:
        for col in loaded_prep.feature_cols:
            val_trans = X_single_trans[col].values[0]
            corr = correlations.get(col, 0.0)
            imp = importances_dict.get(col, 0.0)
            contrib = float(val_trans * corr * imp)
            local_contribs.append({"feature": col, "contribution": contrib})

    local_contribs = sorted(local_contribs, key=lambda x: abs(x["contribution"]), reverse=True)

    print("Top 5 local drivers of churn:")
    for item in local_contribs[:5]:
        direction = "Pushes to Churn (+)" if item['contribution'] > 0 else "Pushes to Stay (-)"
        print(f"- {item['feature']}: {item['contribution']:.4f} ({direction})")

    print("\n=== PIPELINE VALIDATION COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_pipeline_test()
