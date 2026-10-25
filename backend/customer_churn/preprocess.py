import os
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, LabelEncoder

class ChurnPreprocessor:
    def __init__(self):
        self.target_col = None
        self.id_col = None
        self.num_cols = []
        self.cat_cols = []
        self.feature_cols = []

        self.scalers = {}
        self.encoders = {}
        self.imputers = {}  # Store medians and modes

    def detect_columns(self, df, target_col=None):
        """
        Detects ID, numeric, and categorical columns from the dataset.
        """
        # Find target column
        if target_col:
            self.target_col = target_col
        else:
            # Auto-detect target column: look for "churn" case-insensitive
            churn_cols = [c for c in df.columns if "churn" in c.lower()]
            if churn_cols:
                self.target_col = churn_cols[0]
            else:
                raise ValueError("Target column 'Churn' not found. Please specify the target column.")

        # Find ID column: look for columns ending or starting with "id", "key", or "customer"
        id_cols = [c for c in df.columns if c.lower() in ["id", "customerid", "custid", "key"] or c.lower().endswith("id") or c.lower().startswith("id_")]
        if id_cols:
            self.id_col = id_cols[0]
        else:
            self.id_col = None

        # Extract features
        all_cols = list(df.columns)
        if self.target_col in all_cols:
            all_cols.remove(self.target_col)
        if self.id_col and self.id_col in all_cols:
            all_cols.remove(self.id_col)

        self.num_cols = []
        self.cat_cols = []

        for col in all_cols:
            # Check if column is numeric (excluding boolean)
            if pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_bool_dtype(df[col]):
                # If there are very few unique values and it's integer, it might be categorical,
                # but let's treat it as numerical if it is numeric type.
                self.num_cols.append(col)
            else:
                self.cat_cols.append(col)

        self.feature_cols = self.num_cols + self.cat_cols

    def clean_dataframe(self, df):
        """
        Performs basic cleaning like stripping spaces and handling empty strings.
        """
        df_clean = df.copy()

        # Clean string columns: convert empty/space strings to NaN
        for col in df_clean.columns:
            if df_clean[col].dtype == object:
                # Strip whitespace
                df_clean[col] = df_clean[col].astype(str).str.strip()
                # Replace empty strings or "nan" or "none" with NaN
                df_clean[col] = df_clean[col].replace(["", " ", "NaN", "nan", "None", "null", "NULL"], np.nan)

                # Check if a column was incorrectly parsed as object (e.g. TotalCharges with spaces)
                # If we can convert >80% of non-null values to float, convert the column
                non_null = df_clean[col].dropna()
                if len(non_null) > 0:
                    try:
                        converted = pd.to_numeric(non_null, errors='coerce')
                        if converted.notna().sum() / len(non_null) > 0.8:
                            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                    except Exception:
                        pass

        return df_clean

    def fit_transform(self, df, target_col=None):
        """
        Fits the preprocessor to the training dataframe and returns the processed feature matrix and target.
        """
        # Clean first
        df_cleaned = self.clean_dataframe(df)

        # Detect columns
        self.detect_columns(df_cleaned, target_col)

        # Prepare lists for X and y
        X = df_cleaned[self.feature_cols].copy()

        # Handle target column encoding (if Churn is "Yes"/"No" or binary)
        y = None
        if self.target_col in df_cleaned.columns:
            y_raw = df_cleaned[self.target_col].copy()
            # Clean missing values in target by dropping rows
            valid_idx = y_raw.notna()
            X = X[valid_idx]
            y_raw = y_raw[valid_idx]

            # Encode target if not numeric or if boolean
            if not pd.api.types.is_numeric_dtype(y_raw.dtype) or pd.api.types.is_bool_dtype(y_raw.dtype):
                target_encoder = LabelEncoder()
                y = target_encoder.fit_transform(y_raw.astype(str))
                self.encoders[self.target_col] = target_encoder
            else:
                y = y_raw.astype(int).values

        # Fit imputers and transform features
        X_trans = pd.DataFrame(index=X.index)

        # 1. Numerical columns
        for col in self.num_cols:
            # Impute with median
            median_val = X[col].median()
            if pd.isna(median_val):
                median_val = 0.0
            self.imputers[col] = median_val

            col_imputed = X[col].fillna(median_val)

            # Scale
            scaler = StandardScaler()
            col_scaled = scaler.fit_transform(col_imputed.values.reshape(-1, 1)).flatten()
            self.scalers[col] = scaler
            X_trans[col] = col_scaled

        # 2. Categorical columns
        for col in self.cat_cols:
            # Impute with mode (most frequent value)
            mode_series = X[col].mode()
            mode_val = mode_series[0] if not mode_series.empty else "Missing"
            self.imputers[col] = mode_val

            col_imputed = X[col].fillna(mode_val).astype(str)

            # Encode
            le = LabelEncoder()
            col_encoded = le.fit_transform(col_imputed)
            self.encoders[col] = le
            X_trans[col] = col_encoded

        # Return processed features as a DataFrame and target labels
        # Maintain column order of self.feature_cols
        X_trans = X_trans[self.feature_cols]
        return X_trans, y

    def transform(self, df):
        """
        Transforms a new dataframe using the fitted parameters.
        Used for validation and single/batch predictions.
        """
        # Clean first
        df_cleaned = self.clean_dataframe(df)

        # Prepare features DataFrame
        X = pd.DataFrame(index=df_cleaned.index)

        # Align prediction input to the exact feature columns
        for col in self.feature_cols:
            if col in df_cleaned.columns:
                X[col] = df_cleaned[col].copy()
            else:
                # If a feature is missing in the prediction input, fill it with the imputed value
                X[col] = self.imputers.get(col, 0.0 if col in self.num_cols else "Missing")

        X_trans = pd.DataFrame(index=X.index)

        # 1. Numerical columns
        for col in self.num_cols:
            median_val = self.imputers.get(col, 0.0)
            col_imputed = X[col].fillna(median_val)

            scaler = self.scalers.get(col)
            if scaler:
                col_scaled = scaler.transform(col_imputed.values.reshape(-1, 1)).flatten()
            else:
                col_scaled = col_imputed.values
            X_trans[col] = col_scaled

        # 2. Categorical columns
        for col in self.cat_cols:
            mode_val = self.imputers.get(col, "Missing")
            col_imputed = X[col].fillna(mode_val).astype(str)

            le = self.encoders.get(col)
            if le:
                # Handle unseen categories by mapping to the first class or the mode
                # Let's map unseen items to the mode if we can, or encode safely
                classes = list(le.classes_)

                # Check for unseen categories and replace with mode
                mode_class = mode_val if mode_val in classes else classes[0]
                col_imputed_safe = col_imputed.apply(lambda val: val if val in classes else mode_class)

                col_encoded = le.transform(col_imputed_safe)
            else:
                col_encoded = col_imputed.astype('category').cat.codes
            X_trans[col] = col_encoded

        # Maintain column order of self.feature_cols
        X_trans = X_trans[self.feature_cols]
        return X_trans

    def save(self, filepath):
        """
        Saves the fitted preprocessor state using joblib.
        """
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        state = {
            "target_col": self.target_col,
            "id_col": self.id_col,
            "num_cols": self.num_cols,
            "cat_cols": self.cat_cols,
            "feature_cols": self.feature_cols,
            "scalers": self.scalers,
            "encoders": self.encoders,
            "imputers": self.imputers
        }
        joblib.dump(state, filepath)
        print(f"Preprocessor state saved to: {filepath}")

    @classmethod
    def load(cls, filepath):
        """
        Loads the preprocessor state and returns a preprocessor instance.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Preprocessor file not found at: {filepath}")
        state = joblib.load(filepath)

        preprocessor = cls()
        preprocessor.target_col = state["target_col"]
        preprocessor.id_col = state["id_col"]
        preprocessor.num_cols = state["num_cols"]
        preprocessor.cat_cols = state["cat_cols"]
        preprocessor.feature_cols = state["feature_cols"]
        preprocessor.scalers = state["scalers"]
        preprocessor.encoders = state["encoders"]
        preprocessor.imputers = state["imputers"]

        return preprocessor
