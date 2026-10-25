import os
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, roc_curve, confusion_matrix
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC

# Try to import XGBoost
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

def train_and_evaluate_models(X, y, feature_names, test_size=0.2, random_state=42):
    """
    Splits the data, trains multiple classifiers, evaluates them,
    identifies the best model, and returns performance data and plotting coordinates.
    """
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    # Initialize models
    models = {
        "Logistic Regression": LogisticRegression(max_iter=1000, random_state=random_state),
        "Decision Tree": DecisionTreeClassifier(max_depth=5, random_state=random_state),
        "Random Forest": RandomForestClassifier(n_estimators=100, random_state=random_state),
        "Support Vector Machine": SVC(probability=True, random_state=random_state)
    }

    if XGBOOST_AVAILABLE:
        # Use simple CPU parameters
        models["XGBoost"] = xgb.XGBClassifier(
            eval_metric="logloss",
            random_state=random_state
        )

    results = {}
    roc_data = {}
    trained_instances = {}

    for name, model in models.items():
        try:
            # Fit model
            model.fit(X_train, y_train)
            trained_instances[name] = model

            # Predict
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1]

            # Metrics
            acc = accuracy_score(y_test, y_pred)
            prec = precision_score(y_test, y_pred, zero_division=0)
            rec = recall_score(y_test, y_pred, zero_division=0)
            f1 = f1_score(y_test, y_pred, zero_division=0)
            auc = roc_auc_score(y_test, y_prob)

            results[name] = {
                "Accuracy": float(acc),
                "Precision": float(prec),
                "Recall": float(rec),
                "F1 Score": float(f1),
                "ROC-AUC": float(auc)
            }

            # ROC Curve points
            fpr, tpr, _ = roc_curve(y_test, y_prob)
            # Decimate points to reduce payload size if there are too many
            if len(fpr) > 100:
                indices = np.linspace(0, len(fpr) - 1, 100, dtype=int)
                fpr = fpr[indices]
                tpr = tpr[indices]

            roc_data[name] = {
                "fpr": fpr.tolist(),
                "tpr": tpr.tolist(),
                "auc": float(auc)
            }
        except Exception as e:
            print(f"Error training {name}: {str(e)}")

    # Find the best model based on F1 Score
    best_model_name = None
    best_f1 = -1.0
    for name, metrics in results.items():
        if metrics["F1 Score"] > best_f1:
            best_f1 = metrics["F1 Score"]
            best_model_name = name

    best_model = trained_instances[best_model_name]

    # Save the best model
    os.makedirs("models", exist_ok=True)
    best_model_path = os.path.join("models", "best_model.joblib")
    joblib.dump(best_model, best_model_path)

    # Generate Confusion Matrix for the best model
    best_y_pred = best_model.predict(X_test)
    cm = confusion_matrix(y_test, best_y_pred)
    cm_data = {
        "matrix": cm.tolist(),  # [[tn, fp], [fn, tp]]
        "labels": ["Stay", "Churn"]
    }

    # Calculate feature importances for the best model
    importances = get_feature_importances(best_model, feature_names, X_train, y_train)

    # Format results to output
    evaluation = {
        "models_comparison": results,
        "best_model_name": best_model_name,
        "confusion_matrix": cm_data,
        "feature_importance": importances,
        "roc_curves": roc_data
    }

    return evaluation, best_model_path

def get_feature_importances(model, feature_names, X_train=None, y_train=None):
    """
    Extracts feature importances or coefficients from a model.
    """
    importances = []

    try:
        if hasattr(model, "feature_importances_"):
            # Tree-based models (Random Forest, Decision Tree, XGBoost)
            importances = model.feature_importances_.tolist()
        elif hasattr(model, "coef_"):
            # Linear models (Logistic Regression, Linear SVM)
            # Use absolute coefficient weights
            coefs = np.abs(model.coef_[0])
            # Normalize to sum to 1
            if coefs.sum() > 0:
                coefs = coefs / coefs.sum()
            importances = coefs.tolist()
        else:
            # Fallback (e.g. SVM with RBF kernel)
            # Let's compute a simple permutation importance or correlation-based importance
            # For speed, we can return uniform importance, or calculate correlation of each feature with target
            if X_train is not None and y_train is not None:
                # Use absolute correlation of scaled features with the target as fallback
                correlations = []
                for idx in range(X_train.shape[1]):
                    feat = X_train.iloc[:, idx] if isinstance(X_train, pd.DataFrame) else X_train[:, idx]
                    corr = np.abs(np.corrcoef(feat, y_train)[0, 1])
                    if np.isnan(corr):
                        corr = 0.0
                    correlations.append(corr)
                correlations = np.array(correlations)
                if correlations.sum() > 0:
                    correlations = correlations / correlations.sum()
                importances = correlations.tolist()
            else:
                importances = [1.0 / len(feature_names)] * len(feature_names)
    except Exception as e:
        print(f"Error computing feature importances: {str(e)}")
        importances = [1.0 / len(feature_names)] * len(feature_names)

    # Zip names and values, sort descending
    importance_list = [{"feature": name, "importance": float(val)} for name, val in zip(feature_names, importances)]
    importance_list = sorted(importance_list, key=lambda x: x["importance"], reverse=True)

    return importance_list
