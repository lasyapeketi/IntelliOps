"""Feature Engineering Pipeline for Delivery Delay Prediction.

Transforms raw input records into normalized numerical feature representations.
Implements:
- Median imputation for numeric features (fit on train only)
- Most-frequent imputation for categorical features (fit on train only)
- One-hot encoding for shipping_method
- Feature engineering: distance_per_promised_day, historical_delay_ratio
- Standard scaling (fit on train only)
- Strict anti-leakage exclusion of any actual-delivery columns
"""

from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler


BASE_NUMERIC_FEATURES: List[str] = [
    "distance_km",
    "promised_delivery_days",
    "historical_avg_delivery_days",
    "order_volume",
]

CATEGORICAL_FEATURES: List[str] = [
    "shipping_method",
]

SHIPPING_METHOD_CATEGORIES: List[str] = [
    "express",
    "overnight",
    "same_day",
    "standard",
]


class DeliveryDelayFeaturePipeline:
    """End-to-end feature engineering pipeline for delivery delay prediction."""

    def __init__(self) -> None:
        """Initialize transformer components."""
        self.num_imputer = SimpleImputer(strategy="median")
        self.cat_imputer = SimpleImputer(strategy="most_frequent")
        self.one_hot_encoder = OneHotEncoder(
            categories=[SHIPPING_METHOD_CATEGORIES],
            handle_unknown="ignore",
            sparse_output=False,
        )
        self.scaler = StandardScaler()
        self.is_fitted: bool = False
        self._feature_names: List[str] = []

    def _engineer_features(self, df_num: pd.DataFrame) -> pd.DataFrame:
        """Compute domain-specific interaction features.

        - distance_per_promised_day = distance_km / promised_delivery_days
        - historical_delay_ratio = historical_avg_delivery_days / promised_delivery_days
        """
        engineered = df_num.copy()
        # Avoid division by zero with clip
        promised_safe = np.clip(engineered["promised_delivery_days"].values, a_min=1e-5, a_max=None)
        engineered["distance_per_promised_day"] = engineered["distance_km"].values / promised_safe
        engineered["historical_delay_ratio"] = (
            engineered["historical_avg_delivery_days"].values / promised_safe
        )
        return engineered

    def fit(self, X: pd.DataFrame, y: Optional[Union[pd.Series, np.ndarray]] = None) -> "DeliveryDelayFeaturePipeline":
        """Fit imputers, encoder, and scaler on training data ONLY.

        Args:
            X: Training DataFrame containing base features.
            y: Optional target series (ignored).

        Returns:
            self: Fitted instance.
        """
        # Ensure forbidden fields are not present
        forbidden_found = [c for c in X.columns if "actual" in c.lower() or "transit" in c.lower()]
        if forbidden_found:
            raise ValueError(f"Anti-leakage error: Forbidden columns found in feature matrix: {forbidden_found}")

        # 1. Fit numerical imputer
        X_num = X[BASE_NUMERIC_FEATURES].copy()
        self.num_imputer.fit(X_num)
        imputed_num = pd.DataFrame(
            self.num_imputer.transform(X_num),
            columns=BASE_NUMERIC_FEATURES,
            index=X.index,
        )

        # 2. Engineer features on imputed numerical data
        X_engineered = self._engineer_features(imputed_num)

        # 3. Fit categorical imputer and one-hot encoder
        X_cat = X[CATEGORICAL_FEATURES].copy()
        self.cat_imputer.fit(X_cat)
        imputed_cat = self.cat_imputer.transform(X_cat)
        self.one_hot_encoder.fit(imputed_cat)

        cat_encoded_names = [f"shipping_method_{cat}" for cat in SHIPPING_METHOD_CATEGORIES]
        encoded_cat = self.one_hot_encoder.transform(imputed_cat)

        # 4. Combine all features
        all_numeric_features = list(X_engineered.columns)
        combined_features = np.hstack([X_engineered.values, encoded_cat])

        # 5. Fit scaler on combined feature space
        self.scaler.fit(combined_features)

        self._feature_names = all_numeric_features + cat_encoded_names

        # Safety assertion: verify no actual delivery column in feature names
        for name in self._feature_names:
            assert "actual" not in name.lower(), f"Leakage violation in feature names: {name}"

        self.is_fitted = True
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        """Apply pre-fitted transformations to test/inference data without refitting.

        Args:
            X: Input DataFrame.

        Returns:
            np.ndarray: Transformed and scaled feature matrix.
        """
        if not self.is_fitted:
            raise RuntimeError("Pipeline must be fitted on training data before transform is called.")

        # Ensure forbidden fields are not present
        forbidden_found = [c for c in X.columns if "actual" in c.lower() or "transit" in c.lower()]
        if forbidden_found:
            raise ValueError(f"Anti-leakage error: Forbidden columns found in feature matrix: {forbidden_found}")

        # 1. Transform numerical features with pre-fitted imputer (no refitting)
        X_num = X[BASE_NUMERIC_FEATURES].copy()
        imputed_num = pd.DataFrame(
            self.num_imputer.transform(X_num),
            columns=BASE_NUMERIC_FEATURES,
            index=X.index,
        )

        # 2. Engineer interaction features
        X_engineered = self._engineer_features(imputed_num)

        # 3. Transform categorical features with pre-fitted encoder (no refitting)
        X_cat = X[CATEGORICAL_FEATURES].copy()
        imputed_cat = self.cat_imputer.transform(X_cat)
        encoded_cat = self.one_hot_encoder.transform(imputed_cat)

        # 4. Combine and scale with pre-fitted scaler (no refitting)
        combined_features = np.hstack([X_engineered.values, encoded_cat])
        scaled_features = self.scaler.transform(combined_features)

        return scaled_features

    def fit_transform(
        self,
        X: pd.DataFrame,
        y: Optional[Union[pd.Series, np.ndarray]] = None,
    ) -> np.ndarray:
        """Fit pipeline on X and return transformed matrix."""
        return self.fit(X, y).transform(X)

    def get_feature_names(self) -> List[str]:
        """Return list of final engineered and encoded feature names."""
        if not self.is_fitted:
            raise RuntimeError("Pipeline is not fitted yet.")
        return list(self._feature_names)


if __name__ == "__main__":
    from modules.delivery_delay.data_loader import load_raw_dataset
    from modules.delivery_delay.preprocessing import create_target_and_features
    from sklearn.model_selection import train_test_split

    print("Executing feature pipeline demonstration...")
    raw_df, _ = load_raw_dataset(verbose=False)
    X, y = create_target_and_features(raw_df)

    # Train / Test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    # 1. Fit on train ONLY
    pipeline = DeliveryDelayFeaturePipeline()
    X_train_transformed = pipeline.fit_transform(X_train)

    # Record scaler mean before transform on test
    scaler_mean_before = pipeline.scaler.mean_.copy()

    # 2. Transform test data
    X_test_transformed = pipeline.transform(X_test)

    # Record scaler mean after transform on test
    scaler_mean_after = pipeline.scaler.mean_.copy()

    # Verification: scaler must NOT be refit during test transform
    assert np.array_equal(scaler_mean_before, scaler_mean_after), "ERROR: Preprocessor was refitted during test transform!"

    # Verification: check feature names
    feature_names = pipeline.get_feature_names()
    print("\n" + "=" * 60)
    print("FINAL FEATURE LIST:")
    for idx, f in enumerate(feature_names, 1):
        print(f"  {idx}. {f}")
    print("=" * 60)

    # Verify no actual delivery fields in features
    has_leakage = any("actual" in f.lower() for f in feature_names)
    print(f"Contains actual-delivery field: {has_leakage}")
    print(f"Preprocessor refitted on test: {not np.array_equal(scaler_mean_before, scaler_mean_after)}")
    print(f"Train feature shape: {X_train_transformed.shape}")
    print(f"Test feature shape: {X_test_transformed.shape}")
    print("Verification PASSED.")
    print("=" * 60)
