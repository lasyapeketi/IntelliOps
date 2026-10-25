import os
import json
import datetime
import pandas as pd
import numpy as np
import joblib
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for

# Local modules
from preprocess import ChurnPreprocessor
from model import train_and_evaluate_models, get_feature_importances
from report_generator import generate_pdf_report
from data_loader import (
    load_csv, get_excel_sheets, load_excel, load_url, load_huggingface,
    get_sql_tables, load_sql_table, DataLoaderError
)

app = Flask(__name__)
app.secret_key = "customer_churn_prediction_secret_key"

# Configuration
UPLOAD_FOLDER = "uploads"
REPORT_FOLDER = "reports"
MODELS_FOLDER = "models"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)
os.makedirs(MODELS_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload size

# Global state / History in-memory for session-like persistence
# In a real app this would go into a database
prediction_history = []
recent_uploads = []

def get_session_data_path():
    """Returns the file path of currently uploaded dataset."""
    return session.get("current_dataset_path")

@app.route("/")
def index():
    # Gather home statistics
    stats = {
        "total_uploads": len(recent_uploads),
        "total_predictions": len(prediction_history),
        "models_trained": 1 if os.path.exists(os.path.join(MODELS_FOLDER, "best_model.joblib")) else 0,
        "recent_uploads": recent_uploads[:5]
    }
    return render_template("index.html", stats=stats)

@app.route("/upload-page")
def upload_page():
    return render_template("upload.html")

@app.route("/dashboard-page")
def dashboard_page():
    # Renders the dashboard and data analysis layout
    dataset_uploaded = get_session_data_path() is not None
    model_trained = os.path.exists(os.path.join(MODELS_FOLDER, "best_model.joblib"))
    target_col = session.get("target_col", "Churn")
    return render_template("dashboard.html", dataset_uploaded=dataset_uploaded, model_trained=model_trained, target_col=target_col)

@app.route("/prediction-page")
def prediction_page():
    model_trained = os.path.exists(os.path.join(MODELS_FOLDER, "best_model.joblib"))
    # Load categorical levels if available to populate dropdowns dynamically
    cat_levels = {}
    preprocessor_path = os.path.join(MODELS_FOLDER, "preprocessor.joblib")
    if os.path.exists(preprocessor_path):
        try:
            prep = ChurnPreprocessor.load(preprocessor_path)
            # Gather classes from label encoders
            for col, encoder in prep.encoders.items():
                if col != prep.target_col:
                    cat_levels[col] = list(encoder.classes_)
        except Exception as e:
            print(f"Error reading preprocessor: {e}")

    # Default values fallback if preprocessor is not loaded yet
    if not cat_levels:
        cat_levels = {
            "gender": ["Female", "Male"],
            "Partner": ["No", "Yes"],
            "Dependents": ["No", "Yes"],
            "PhoneService": ["No", "Yes"],
            "MultipleLines": ["No", "Yes", "No phone service"],
            "InternetService": ["DSL", "Fiber optic", "No"],
            "OnlineSecurity": ["No", "Yes", "No internet service"],
            "OnlineBackup": ["No", "Yes", "No internet service"],
            "DeviceProtection": ["No", "Yes", "No internet service"],
            "TechSupport": ["No", "Yes", "No internet service"],
            "StreamingTV": ["No", "Yes", "No internet service"],
            "StreamingMovies": ["No", "Yes", "No internet service"],
            "Contract": ["Month-to-month", "One year", "Two year"],
            "PaperlessBilling": ["No", "Yes"],
            "PaymentMethod": ["Electronic check", "Mailed check", "Bank transfer (automatic)", "Credit card (automatic)"]
        }

    return render_template("prediction.html", model_trained=model_trained, cat_levels=cat_levels)

def save_and_register_dataset(df, source_type, dataset_name):
    """
    Saves loaded DataFrame to standard upload storage, updates session and history,
    and returns a unified preview payload with first 50 rows, data types, and missing values.
    """
    import re
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        raise DataLoaderError("❌ The loaded dataset is empty or invalid.")

    # Sanitize dataset name
    safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', str(dataset_name))
    if not safe_name.lower().endswith(".csv"):
        safe_name = f"{safe_name}.csv"

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{safe_name}"
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    # Persist as standardized CSV for downstream ML compatibility
    df.to_csv(file_path, index=False)

    rows, cols = int(df.shape[0]), int(df.shape[1])

    # Check target column
    target_col = None
    churn_cols = [c for c in df.columns if "churn" in str(c).lower()]
    if churn_cols:
        target_col = churn_cols[0]
        session["target_col"] = target_col
        target_found = True
    else:
        session["target_col"] = None
        target_found = False

    session["current_dataset_path"] = file_path
    session["uploaded_filename"] = dataset_name
    session["data_source"] = source_type

    # Update history
    upload_info = {
        "filename": dataset_name,
        "source": source_type,
        "rows": rows,
        "columns": cols,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "path": file_path
    }
    recent_uploads.insert(0, upload_info)

    # First 50 rows preview
    preview_df = df.head(50).fillna("")

    # Data types and missing counts
    dtypes = {str(col): str(dtype) for col, dtype in df.dtypes.items()}
    missing_counts = {str(col): int(df[col].isnull().sum()) for col in df.columns}
    total_missing = int(df.isnull().sum().sum())

    preview_data = {
        "source": source_type,
        "dataset_name": dataset_name,
        "columns": [str(c) for c in preview_df.columns],
        "rows": preview_df.values.tolist(),
        "shape": [rows, cols],
        "rows_formatted": f"{rows:,}",
        "dtypes": dtypes,
        "missing_counts": missing_counts,
        "total_missing": total_missing,
        "target_detected": target_found,
        "detected_target": target_col,
        "all_columns": [str(c) for c in df.columns]
    }
    return preview_data

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "❌ No file part in the request"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "❌ No file selected"}), 400

    if not file.filename.lower().endswith(".csv"):
        return jsonify({"success": False, "error": "❌ Invalid file format. Please upload a CSV file."}), 400

    try:
        df = load_csv(file)
        preview_data = save_and_register_dataset(df, "CSV", file.filename)
        return jsonify({"success": True, "data": preview_data})
    except DataLoaderError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": "❌ Could not load the dataset. Please check the file format or URL."}), 500

@app.route("/upload-excel", methods=["POST"])
def upload_excel():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "❌ No file uploaded."}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "❌ No file selected."}), 400

    lower_name = file.filename.lower()
    if not (lower_name.endswith(".xlsx") or lower_name.endswith(".xls")):
        return jsonify({"success": False, "error": "❌ Supported formats: .xlsx, .xls"}), 400

    sheet_name = request.form.get("sheet_name")

    try:
        temp_path = os.path.join(app.config["UPLOAD_FOLDER"], f"temp_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        file.save(temp_path)

        sheets = get_excel_sheets(temp_path)

        # If multiple sheets and no specific sheet requested, return sheet choices
        if len(sheets) > 1 and not sheet_name:
            return jsonify({
                "success": True,
                "needs_sheet_selection": True,
                "sheets": sheets,
                "temp_filename": os.path.basename(temp_path),
                "original_filename": file.filename
            })

        # Load the sheet
        target_sheet = sheet_name if (sheet_name and sheet_name in sheets) else sheets[0]
        df = load_excel(temp_path, sheet_name=target_sheet)

        try:
            os.remove(temp_path)
        except OSError:
            pass

        display_name = f"{file.filename} [{target_sheet}]" if len(sheets) > 1 else file.filename
        preview_data = save_and_register_dataset(df, "Excel", display_name)
        return jsonify({"success": True, "data": preview_data})

    except DataLoaderError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception:
        return jsonify({"success": False, "error": "❌ Could not load the dataset. Please check the file format or URL."}), 500

@app.route("/select-excel-sheet", methods=["POST"])
def select_excel_sheet():
    data = request.get_json() or {}
    temp_filename = data.get("temp_filename")
    original_filename = data.get("original_filename", "workbook.xlsx")
    sheet_name = data.get("sheet_name")

    if not temp_filename:
        return jsonify({"success": False, "error": "❌ Missing file reference."}), 400

    temp_path = os.path.join(app.config["UPLOAD_FOLDER"], os.path.basename(temp_filename))
    if not os.path.exists(temp_path):
        return jsonify({"success": False, "error": "❌ Temporary Excel file expired. Please re-upload."}), 400

    try:
        df = load_excel(temp_path, sheet_name=sheet_name)
        try:
            os.remove(temp_path)
        except OSError:
            pass

        display_name = f"{original_filename} [{sheet_name}]" if sheet_name else original_filename
        preview_data = save_and_register_dataset(df, "Excel", display_name)
        return jsonify({"success": True, "data": preview_data})

    except DataLoaderError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception:
        return jsonify({"success": False, "error": "❌ Could not load the dataset. Please check the file format or URL."}), 500

@app.route("/load-url", methods=["POST"])
def load_dataset_url():
    import urllib.parse
    data = request.get_json() or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"success": False, "error": "❌ Please paste a valid dataset URL."}), 400

    try:
        df = load_url(url)
        parsed = urllib.parse.urlparse(url)
        path_name = os.path.basename(parsed.path) or "remote_dataset"
        preview_data = save_and_register_dataset(df, "Dataset URL", path_name)
        return jsonify({"success": True, "data": preview_data})

    except DataLoaderError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception:
        return jsonify({"success": False, "error": "❌ Could not load the dataset. Please check the file format or URL."}), 500

@app.route("/load-huggingface", methods=["POST"])
def load_hf_dataset():
    data = request.get_json() or {}
    dataset_id = data.get("dataset_id", "").strip()

    if not dataset_id:
        return jsonify({"success": False, "error": "❌ Please enter a Hugging Face Dataset ID."}), 400

    try:
        df = load_huggingface(dataset_id)
        preview_data = save_and_register_dataset(df, "Hugging Face", dataset_id)
        return jsonify({"success": True, "data": preview_data})

    except DataLoaderError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception:
        return jsonify({"success": False, "error": "❌ Dataset could not be found on Hugging Face. Check the dataset ID and try again."}), 500

@app.route("/sql-connect", methods=["POST"])
def sql_connect():
    db_type = request.form.get("db_type") or (request.get_json() or {}).get("db_type", "sqlite")
    db_type = db_type.strip().lower()

    sqlite_file_path = None
    connection_params = {}

    if db_type == "sqlite":
        if "file" in request.files:
            file = request.files["file"]
            if file.filename != "":
                filename = f"sqlite_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
                sqlite_file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(sqlite_file_path)
        else:
            raw_path = request.form.get("sqlite_path") or (request.get_json() or {}).get("sqlite_path")
            if raw_path and os.path.exists(raw_path):
                sqlite_file_path = raw_path

        if not sqlite_file_path or not os.path.exists(sqlite_file_path):
            return jsonify({"success": False, "error": "❌ Please upload or select a valid SQLite .db or .sqlite file."}), 400

        session["last_sqlite_file"] = sqlite_file_path

    else:
        data = request.get_json() if request.is_json else request.form.to_dict()
        connection_params = {
            "host": data.get("host", "localhost"),
            "port": int(data.get("port") or (3306 if "mysql" in db_type else 5432)),
            "database": data.get("database", ""),
            "username": data.get("username", ""),
            "password": data.get("password", "")
        }
        session["db_connection_params"] = {
            "db_type": db_type,
            "host": connection_params["host"],
            "port": connection_params["port"],
            "database": connection_params["database"],
            "username": connection_params["username"],
            "password": connection_params["password"]
        }

    try:
        tables = get_sql_tables(db_type, connection_params=connection_params, sqlite_file=sqlite_file_path)
        return jsonify({
            "success": True,
            "tables": tables,
            "db_type": db_type,
            "sqlite_file": sqlite_file_path
        })

    except DataLoaderError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception:
        return jsonify({"success": False, "error": "❌ Unable to connect to the database. Please verify the connection details."}), 500

@app.route("/load-sql", methods=["POST"])
def load_sql():
    data = request.get_json() or request.form.to_dict()
    table_name = data.get("table_name")
    db_type = data.get("db_type") or session.get("db_connection_params", {}).get("db_type", "sqlite")
    db_type = db_type.strip().lower()

    if not table_name:
        return jsonify({"success": False, "error": "❌ Please select a table to load."}), 400

    sqlite_file_path = data.get("sqlite_file") or session.get("last_sqlite_file")
    connection_params = session.get("db_connection_params", {})

    try:
        df = load_sql_table(db_type, connection_params=connection_params, table_name=table_name, sqlite_file=sqlite_file_path)

        if "db_connection_params" in session:
            session["db_connection_params"]["password"] = ""

        display_name = f"{table_name} ({db_type.upper()})"
        preview_data = save_and_register_dataset(df, f"SQL Database ({db_type.capitalize()})", display_name)
        return jsonify({"success": True, "data": preview_data})

    except DataLoaderError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception:
        return jsonify({"success": False, "error": "❌ Unable to connect to the database. Please verify the connection details."}), 500

@app.route("/select-target", methods=["POST"])
def select_target():
    data = request.get_json() or {}
    target_col = data.get("target_col")
    file_path = get_session_data_path()

    if not file_path or not os.path.exists(file_path):
        return jsonify({"success": False, "error": "❌ No uploaded dataset found."}), 400

    try:
        df = pd.read_csv(file_path)
        if target_col not in df.columns:
            return jsonify({"success": False, "error": f"❌ Column '{target_col}' not found in dataset."}), 400

        session["target_col"] = target_col
        rows, cols = int(df.shape[0]), int(df.shape[1])

        preview_df = df.head(50).fillna("")
        dtypes = {str(col): str(dtype) for col, dtype in df.dtypes.items()}
        missing_counts = {str(col): int(df[col].isnull().sum()) for col in df.columns}
        total_missing = int(df.isnull().sum().sum())

        preview_data = {
            "source": session.get("data_source", "Uploaded Dataset"),
            "dataset_name": session.get("uploaded_filename", "Current Dataset"),
            "columns": [str(c) for c in preview_df.columns],
            "rows": preview_df.values.tolist(),
            "shape": [rows, cols],
            "rows_formatted": f"{rows:,}",
            "dtypes": dtypes,
            "missing_counts": missing_counts,
            "total_missing": total_missing,
            "target_detected": True,
            "detected_target": target_col,
            "all_columns": [str(c) for c in df.columns]
        }
        return jsonify({"success": True, "data": preview_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/analyze", methods=["GET"])
def analyze_data():
    file_path = get_session_data_path()
    if not file_path or not os.path.exists(file_path):
        return jsonify({"success": False, "error": "No active dataset found. Please upload one first."}), 400

    target_col = session.get("target_col")
    if not target_col:
        return jsonify({"success": False, "error": "Target column not set."}), 400

    try:
        df = pd.read_csv(file_path)
        rows, cols = df.shape

        # 1. Missing values & data types
        missing_counts = df.isnull().sum().to_dict()
        data_types = {k: str(v) for k, v in df.dtypes.to_dict().items()}
        duplicates = int(df.duplicated().sum())

        # 2. Numerical Summary
        num_summary = df.describe().fillna("").to_dict()

        # 3. Create distributions for Plotly rendering
        # Churn/Target distribution
        target_counts = df[target_col].value_counts().to_dict()
        target_dist = {
            "labels": list(target_counts.keys()),
            "values": [int(v) for v in target_counts.values()]
        }

        # Demographic distributions (e.g. Contract, PaymentMethod, InternetService vs Target)
        categorical_plots = {}
        for col in ["Contract", "PaymentMethod", "InternetService", "gender"]:
            if col in df.columns:
                ct = pd.crosstab(df[col], df[target_col]).fillna(0)
                categorical_plots[col] = {
                    "categories": list(ct.index),
                    "churn_no": [int(x) for x in ct.iloc[:, 0]] if ct.shape[1] > 0 else [],
                    "churn_yes": [int(x) for x in ct.iloc[:, 1]] if ct.shape[1] > 1 else []
                }

        # Histograms for charges and tenure
        histograms = {}
        for col in ["MonthlyCharges", "tenure", "TotalCharges"]:
            if col in df.columns:
                # Convert TotalCharges to float if it is object
                s = df[col]
                if s.dtype == object:
                    s = pd.to_numeric(s.str.strip().replace(["", " "], np.nan), errors='coerce')
                s = s.dropna()

                # Split by target
                y_val = df.loc[s.index, target_col].astype(str)
                stay_vals = s[y_val.str.lower().isin(["no", "0", "false"])].tolist()
                churn_vals = s[y_val.str.lower().isin(["yes", "1", "true"])].tolist()

                histograms[col] = {
                    "stay": stay_vals[:500],  # Limit to 500 samples to keep JSON payload lightweight
                    "churn": churn_vals[:500]
                }

        # Correlation Matrix
        numeric_df = df.select_dtypes(include=[np.number])
        # Include target column if we can map it to 0/1
        if target_col in df.columns:
            # Map Yes/No or Churn/Stay to 1/0
            mapped_target = df[target_col].astype(str).str.lower().map({"yes": 1, "1": 1, "true": 1, "no": 0, "0": 0, "false": 0}).fillna(0)
            numeric_df = numeric_df.copy()
            numeric_df[target_col] = mapped_target

        corr_matrix = numeric_df.corr().fillna(0)
        corr_data = {
            "z": corr_matrix.values.tolist(),
            "x": list(corr_matrix.columns),
            "y": list(corr_matrix.index)
        }

        analysis_data = {
            "rows": rows,
            "columns": cols,
            "duplicates": duplicates,
            "missing_values": missing_counts,
            "data_types": data_types,
            "num_summary": num_summary,
            "target_dist": target_dist,
            "categorical_plots": categorical_plots,
            "histograms": histograms,
            "correlation_matrix": corr_data
        }
        return jsonify({"success": True, "data": analysis_data})

    except Exception as e:
        return jsonify({"success": False, "error": f"Error running data profiling: {str(e)}"}), 500

@app.route("/train", methods=["POST"])
def train_model():
    file_path = get_session_data_path()
    if not file_path or not os.path.exists(file_path):
        return jsonify({"success": False, "error": "No active dataset. Upload CSV first."}), 400

    target_col = session.get("target_col")
    if not target_col:
        return jsonify({"success": False, "error": "Target column not set. Please upload file or select target."}), 400

    try:
        df = pd.read_csv(file_path)

        # Fit Preprocessor
        preprocessor = ChurnPreprocessor()
        X_trans, y = preprocessor.fit_transform(df, target_col)

        # Save preprocessor state
        prep_path = os.path.join(MODELS_FOLDER, "preprocessor.joblib")
        preprocessor.save(prep_path)

        # Train and evaluate models
        evaluation, best_model_path = train_and_evaluate_models(X_trans, y, preprocessor.feature_cols)

        # Save correlation weights for local explainability
        # Compute correlation of preprocessed features with target y
        feature_correlations = {}
        for idx, col in enumerate(preprocessor.feature_cols):
            feat_values = X_trans[col].values
            corr = np.corrcoef(feat_values, y)[0, 1]
            if np.isnan(corr):
                corr = 0.0
            feature_correlations[col] = float(corr)

        # Update preprocessor with correlations and save again
        preprocessor_state = joblib.load(prep_path)
        preprocessor_state["feature_correlations"] = feature_correlations
        joblib.dump(preprocessor_state, prep_path)

        # Keep details in session for prediction page
        session["best_model_name"] = evaluation["best_model_name"]

        return jsonify({"success": True, "data": evaluation})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Error during model training: {str(e)}"}), 500

def get_local_explainable_ai(prep, model, customer_trans_df, customer_raw_df):
    """
    Computes local feature contributions for a single customer prediction.
    """
    feature_names = prep.feature_cols

    # Reload preprocessor state to get correlations
    prep_path = os.path.join(MODELS_FOLDER, "preprocessor.joblib")
    preprocessor_state = joblib.load(prep_path)
    feature_correlations = preprocessor_state.get("feature_correlations", {})

    # Get global feature importances
    global_importances = get_feature_importances(model, feature_names)
    importances_dict = {item["feature"]: item["importance"] for item in global_importances}

    local_contribs = []

    # Logistic Regression has coefficients
    is_lr = hasattr(model, "coef_")
    if is_lr:
        coefs = model.coef_[0]
        # contribution = coef_i * X_scaled_i
        for idx, col in enumerate(feature_names):
            val_trans = customer_trans_df[col].values[0]
            val_raw = customer_raw_df[col].values[0] if col in customer_raw_df.columns else "N/A"
            contrib = float(coefs[idx] * val_trans)
            local_contribs.append({
                "feature": col,
                "raw_value": str(val_raw),
                "contribution": contrib
            })
    else:
        # General model fallback using: scaled_val * correlation * global_importance
        for col in feature_names:
            val_trans = customer_trans_df[col].values[0]
            val_raw = customer_raw_df[col].values[0] if col in customer_raw_df.columns else "N/A"

            corr = feature_correlations.get(col, 0.0)
            imp = importances_dict.get(col, 0.0)

            # The contribution scales with feature value, direction aligns with correlation,
            # and magnitude aligns with feature importance.
            contrib = float(val_trans * corr * imp)
            local_contribs.append({
                "feature": col,
                "raw_value": str(val_raw),
                "contribution": contrib
            })

    # Sort contributions by absolute value
    local_contribs = sorted(local_contribs, key=lambda x: abs(x["contribution"]), reverse=True)
    return local_contribs

def generate_insights_and_recommendations(prediction, local_contribs):
    """
    Generates AI-style retention recommendations based on top churn drivers.
    """
    insights = []
    recommendations = []

    # Filter features that pushed prediction TOWARDS churn (positive contribution)
    churn_drivers = [item for item in local_contribs if item["contribution"] > 0.05]

    # If customer is predicted to stay, we can focus on top potential risk factors
    if prediction == "Stay":
        churn_drivers = [item for item in local_contribs if item["contribution"] > 0.01]

    drivers_names = [item["feature"].lower() for item in churn_drivers[:3]]

    # Generate insights text
    if not churn_drivers:
        insights.append("No significant churn risk factors detected. Account is highly stable.")
        recommendations.append("Standard Loyalty Campaign: Maintain regular contact and monitor satisfaction scores.")
    else:
        # Construct insight
        insights.append(f"Top risk drivers include: {', '.join([item['feature'] + ' (' + str(item['raw_value']) + ')' for item in churn_drivers[:3]])}.")

        # Check specific features and add corresponding recommendations
        for item in churn_drivers[:4]:
            feat = item["feature"].lower()
            val = str(item["raw_value"]).lower()

            if "contract" in feat and "month-to-month" in val:
                insights.append("Month-to-month contract provides no long-term customer lock-in.")
                recommendations.append("Contract Upgrade: Propose a 1-year or 2-year contract with a monthly discount (e.g. 10%) to secure long-term loyalty.")
            elif "monthlycharges" in feat:
                insights.append("Monthly charges are high compared to average customer rates.")
                recommendations.append("Loyalty Pricing: Offer a loyalty discount or bundle check-up to ensure pricing satisfaction.")
            elif "internetservice" in feat and "fiber optic" in val:
                insights.append("Fiber optic internet has higher churn ratios, possibly due to support issues or cost.")
                recommendations.append("Service Health-check: Proactively inspect line quality or offer a free tech-support checkup.")
            elif "onlinebackup" in feat and "no" in val:
                recommendations.append("Cross-Sell Incentive: Offer a 3-month free trial of Online Backup to improve user stickiness.")
            elif "techsupport" in feat and "no" in val:
                insights.append("Customer lacks Tech Support addon, increasing vulnerability during service issues.")
                recommendations.append("Priority Support: Bundle basic tech support or provide a free priority support upgrade.")
            elif "paymentmethod" in feat and "electronic check" in val:
                recommendations.append("Auto-Pay Promotion: Offer a one-time $5 credit to migrate billing to Auto-pay Credit Card or Bank Transfer.")
            elif "tenure" in feat:
                # low tenure
                try:
                    ten = int(item["raw_value"])
                    if ten <= 6:
                        insights.append("New customer in critical onboarding window (under 6 months tenure).")
                        recommendations.append("Onboarding VIP Program: Schedule a customer success call to resolve early installation or usage friction.")
                except ValueError:
                    pass

    # Fill in default recommendations if sparse
    if len(recommendations) < 2:
        recommendations.append("Proactive Outreach: Contact customer to evaluate overall service satisfaction.")
    if len(recommendations) < 3:
        recommendations.append("Loyalty Program: Offer enrollment in the customer appreciation program.")

    return insights, recommendations

@app.route("/predict-single", methods=["POST"])
def predict_single():
    model_path = os.path.join(MODELS_FOLDER, "best_model.joblib")
    prep_path = os.path.join(MODELS_FOLDER, "preprocessor.joblib")

    if not os.path.exists(model_path) or not os.path.exists(prep_path):
        return jsonify({"success": False, "error": "Model or preprocessor not found. Please train models first."}), 400

    try:
        # Load form data
        form_data = request.form.to_dict()

        # In case the user passed JSON
        if not form_data and request.get_json():
            form_data = request.get_json()

        # Parse numeric inputs
        for num_col in ["tenure", "MonthlyCharges", "TotalCharges", "SeniorCitizen"]:
            if num_col in form_data:
                # Check for empty value
                val = form_data[num_col].strip()
                if val == "":
                    form_data[num_col] = np.nan
                else:
                    form_data[num_col] = float(val)

        # Construct DataFrame
        df_single = pd.DataFrame([form_data])

        # Load pipeline artifacts
        prep = ChurnPreprocessor.load(prep_path)
        model = joblib.load(model_path)

        # Transform
        X_trans = prep.transform(df_single)

        # Predict
        prob = float(model.predict_proba(X_trans)[0][1])
        pred_label = "Churn" if prob >= 0.5 else "Stay"

        # Explainable AI
        local_contribs = get_local_explainable_ai(prep, model, X_trans, df_single)

        # AI Insights & Recommendations
        insights, recommendations = generate_insights_and_recommendations(pred_label, local_contribs)

        result = {
            "prediction": pred_label,
            "probability": prob,
            "confidence_percentage": round(prob * 100 if pred_label == "Churn" else (1 - prob) * 100, 1),
            "explainability": local_contribs[:8],  # Return top 8 factors
            "insights": insights,
            "recommendations": recommendations,
            "customer_details": form_data
        }

        # Add to history
        hist_entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "Single Customer",
            "identifier": form_data.get("customerID", "MANUAL-CUST"),
            "prediction": pred_label,
            "probability": prob,
            "model_used": session.get("best_model_name", "Best Model")
        }
        prediction_history.insert(0, hist_entry)

        return jsonify({"success": True, "data": result})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Error running single prediction: {str(e)}"}), 500

@app.route("/predict-batch", methods=["POST"])
def predict_batch():
    model_path = os.path.join(MODELS_FOLDER, "best_model.joblib")
    prep_path = os.path.join(MODELS_FOLDER, "preprocessor.joblib")

    if not os.path.exists(model_path) or not os.path.exists(prep_path):
        return jsonify({"success": False, "error": "Model or preprocessor not trained. Please train models first."}), 400

    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected."}), 400

    try:
        # Load CSV
        df = pd.read_csv(file)

        # Save upload to uploads folder
        filename = f"batch_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        df.to_csv(file_path, index=False)

        # Load preprocessor & model
        prep = ChurnPreprocessor.load(prep_path)
        model = joblib.load(model_path)

        # Preprocess dataset
        X_trans = prep.transform(df)

        # Predict
        probs = model.predict_proba(X_trans)[:, 1]
        preds = ["Churn" if p >= 0.5 else "Stay" for p in probs]

        # Add predictions back to dataframe
        df_predictions = df.copy()

        # Ensure CustomerID is present, generate if not
        id_col = prep.id_col if prep.id_col and prep.id_col in df_predictions.columns else None
        if not id_col:
            # Look for case-insensitive matches for customerID
            id_cols = [c for c in df_predictions.columns if "id" in c.lower()]
            if id_cols:
                id_col = id_cols[0]
            else:
                df_predictions["customerID"] = [f"CUST-{idx+1000}" for idx in range(len(df_predictions))]
                id_col = "customerID"

        df_predictions["prediction"] = preds
        df_predictions["probability"] = probs

        # Risk levels
        risk_categories = []
        for p in probs:
            if p >= 0.8:
                risk_categories.append("High Risk")
            elif p >= 0.5:
                risk_categories.append("Medium Risk")
            else:
                risk_categories.append("Low Risk")
        df_predictions["risk_category"] = risk_categories

        # Compute aggregated summary metrics
        total = len(df_predictions)
        churn_count = int(np.sum(np.array(preds) == "Churn"))
        stay_count = total - churn_count
        churn_rate = float(churn_count / total * 100) if total > 0 else 0.0

        # Avg prediction confidence: if Churn, use prob. If Stay, use 1-prob
        confidences = [p if preds[i] == "Churn" else 1.0 - p for i, p in enumerate(probs)]
        avg_confidence = float(np.mean(confidences) * 100) if total > 0 else 0.0

        # Keep in-session to download PDF / CSV
        batch_results_path = os.path.join(REPORT_FOLDER, f"batch_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        df_predictions.to_csv(batch_results_path, index=False)
        session["last_batch_results_path"] = batch_results_path

        # Build Summary Data
        summary = {
            "total_customers": total,
            "churn_count": churn_count,
            "stay_count": stay_count,
            "churn_rate": churn_rate,
            "avg_confidence": avg_confidence,
            "high_risk_count": int(np.sum(np.array(risk_categories) == "High Risk")),
            "medium_risk_count": int(np.sum(np.array(risk_categories) == "Medium Risk")),
            "low_risk_count": int(np.sum(np.array(risk_categories) == "Low Risk"))
        }

        # Generate global AI recommendations for the report summary
        # Gather top features driving churn across the batch
        # We can sum absolute local contributions of the churned subset
        df_churned = df_predictions[df_predictions["prediction"] == "Churn"]
        insights = []
        recommendations = []

        if len(df_churned) > 0:
            # Run preprocessor on churned subset to examine factors
            X_trans_churned = prep.transform(df_churned)
            # Find columns with highest correlation or mean value
            # Standard heuristics for our report
            if "Contract" in df_churned.columns:
                m2m_pct = (df_churned["Contract"] == "Month-to-month").mean() * 100
                if m2m_pct > 50:
                    insights.append(f"{m2m_pct:.1f}% of churned customers are on Month-to-Month contracts.")
                    recommendations.append("Contract upgrades: Offer Month-to-Month customers contract incentives.")
            if "InternetService" in df_churned.columns:
                fo_pct = (df_churned["InternetService"] == "Fiber optic").mean() * 100
                if fo_pct > 40:
                    insights.append(f"{fo_pct:.1f}% of churned customers subscribe to Fiber Optic internet.")
                    recommendations.append("Fiber optic support review: Troubleshoot connectivity and review fiber pricing models.")
            if "MonthlyCharges" in df_churned.columns:
                mean_charges_churn = df_churned["MonthlyCharges"].mean()
                mean_charges_stay = df_predictions[df_predictions["prediction"] == "Stay"]["MonthlyCharges"].mean() if stay_count > 0 else 0.0
                if mean_charges_churn > mean_charges_stay:
                    insights.append(f"Churned accounts pay higher monthly rates on average (${mean_charges_churn:.2f} vs ${mean_charges_stay:.2f}).")
                    recommendations.append("Price elasticity discounts: Proactively review high-spending churn-risk targets.")
            if "TechSupport" in df_churned.columns:
                no_support_pct = (df_churned["TechSupport"] == "No").mean() * 100
                if no_support_pct > 60:
                    insights.append(f"{no_support_pct:.1f}% of churned accounts lack premium Tech Support.")
                    recommendations.append("Premium Support bundling: Propose bundled Tech Support packages to new signups.")

        summary["insights"] = insights
        summary["recommendations"] = recommendations

        # Save summary in session
        session["last_batch_summary"] = summary

        # Format list results for table JSON (return top 100 for safety, frontend does client side paging/filtering)
        output_records = []
        for idx, row in df_predictions.head(200).iterrows():
            output_records.append({
                "customerID": str(row.get(id_col, f"CUST-{idx}")),
                "prediction": str(row.get("prediction")),
                "probability": float(row.get("probability")),
                "risk_category": str(row.get("risk_category")),
                # Include some raw metadata columns if present
                "tenure": int(row.get("tenure", 0)) if "tenure" in row else "N/A",
                "MonthlyCharges": float(row.get("MonthlyCharges", 0.0)) if "MonthlyCharges" in row else "N/A",
                "Contract": str(row.get("Contract", "N/A"))
            })

        # Update history
        hist_entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "Batch Prediction",
            "identifier": file.filename,
            "prediction": f"{churn_count} Churned / {stay_count} Stay",
            "probability": churn_rate / 100.0,
            "model_used": session.get("best_model_name", "Best Model")
        }
        prediction_history.insert(0, hist_entry)

        return jsonify({
            "success": True,
            "summary": summary,
            "predictions": output_records
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Error running batch prediction: {str(e)}"}), 500

@app.route("/export-csv", methods=["GET"])
def export_csv():
    batch_path = session.get("last_batch_results_path")
    if not batch_path or not os.path.exists(batch_path):
        return "No batch prediction results found.", 404

    return send_file(
        batch_path,
        mimetype="text/csv",
        as_attachment=True,
        download_name="churn_predictions_export.csv"
    )

@app.route("/download-pdf", methods=["GET"])
def download_pdf():
    batch_path = session.get("last_batch_results_path")
    summary = session.get("last_batch_summary")

    if not batch_path or not os.path.exists(batch_path) or not summary:
        return "No batch prediction results found. Please complete a batch prediction first.", 404

    try:
        df_predictions = pd.read_csv(batch_path)
        pdf_path = os.path.join(REPORT_FOLDER, "churn_prediction_report.pdf")

        generate_pdf_report(summary, df_predictions, pdf_path)

        return send_file(
            pdf_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="churn_prediction_executive_report.pdf"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error generating PDF report: {str(e)}", 500

@app.route("/prediction-history", methods=["GET"])
def get_history():
    return jsonify({"success": True, "history": prediction_history})

@app.route("/recent-uploads", methods=["GET"])
def get_recent_uploads():
    return jsonify({"success": True, "uploads": recent_uploads})

# Initialize by generating mock dataset if not present
mock_data_path = "dataset/sample_churn.csv"
if not os.path.exists(mock_data_path):
    print("No sample dataset detected. Generating mock churn dataset...")
    try:
        from dataset.generate_mock_data import generate_mock_churn_data
        generate_mock_churn_data(mock_data_path, 1000)
    except Exception as e:
        print(f"Error generating sample dataset: {e}")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
