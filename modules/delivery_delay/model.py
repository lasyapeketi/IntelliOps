"""Machine Learning Model Definition and Serialization for Delivery Delay Prediction.

Provides:
- RandomForest classifier training and hyperparameter configuration
- Feature importance calculation and ranking
- Unified serialization of model estimator + feature pipeline as version 1.0 "delivery-delay-model"
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier


class DeliveryDelayModel:
    """Wrapper encapsulating the trained RandomForest estimator, feature pipeline, and metadata."""

    def __init__(
        self,
        model_name: str = "delivery-delay-model",
        version: str = "1.0",
    ) -> None:
        """Initialize model wrapper.

        Args:
            model_name: Fixed model name ("delivery-delay-model").
            version: Model version identifier ("1.0").
        """
        self.model_name: str = model_name
        self.version: str = version
        self.estimator: Optional[RandomForestClassifier] = None
        self.feature_pipeline: Optional[Any] = None
        self.feature_importances: Dict[str, float] = {}
        self.top_factors: List[Tuple[str, float]] = []

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        feature_pipeline: Any,
        n_estimators: int = 100,
        max_depth: Optional[int] = 5,
        random_state: int = 42,
    ) -> Dict[str, Any]:
        """Train RandomForest classifier and extract feature importances.

        Args:
            X_train: Preprocessed numerical feature matrix.
            y_train: Binary target vector (0 = on_time, 1 = delayed).
            feature_pipeline: Fitted feature pipeline transformer.
            n_estimators: Number of decision trees.
            max_depth: Maximum tree depth to control overfitting.
            random_state: Reproducibility seed.

        Returns:
            Dictionary with training summary and feature importances.
        """
        self.feature_pipeline = feature_pipeline

        # Initialize and fit RandomForest classifier
        self.estimator = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
            min_samples_split=3,
            min_samples_leaf=2,
            class_weight="balanced",
        )
        self.estimator.fit(X_train, y_train)

        # Map feature importances to engineered feature names
        feature_names = feature_pipeline.get_feature_names()
        importances = self.estimator.feature_importances_

        self.feature_importances = {
            name: float(round(imp, 4)) for name, imp in zip(feature_names, importances)
        }

        # Sort top factors descending
        self.top_factors = sorted(
            self.feature_importances.items(), key=lambda x: x[1], reverse=True
        )

        return {
            "model_name": self.model_name,
            "version": self.version,
            "top_factors": self.top_factors,
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict binary class labels (0 or 1)."""
        if self.estimator is None:
            raise RuntimeError("Model is not trained or loaded.")
        return self.estimator.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probability distribution."""
        if self.estimator is None:
            raise RuntimeError("Model is not trained or loaded.")
        return self.estimator.predict_proba(X)

    def get_top_features(self, top_k: int = 5) -> List[Tuple[str, float]]:
        """Return the top-K highest contributing features."""
        return self.top_factors[:top_k]

    def save(self, filepath: Optional[str] = None) -> str:
        """Serialize model, feature pipeline, and metadata together to disk.

        Args:
            filepath: Destination path. Defaults to modules/delivery_delay/artifacts/delivery_delay_model_v1.joblib

        Returns:
            Absolute filepath string where artifact was saved.
        """
        if self.estimator is None or self.feature_pipeline is None:
            raise RuntimeError("Cannot save an uninitialized model.")

        if filepath is None:
            artifact_dir = Path(__file__).parent / "artifacts"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            filepath = str(artifact_dir / "delivery_delay_model_v1.joblib")

        payload = {
            "model_name": self.model_name,
            "version": self.version,
            "estimator": self.estimator,
            "feature_pipeline": self.feature_pipeline,
            "feature_importances": self.feature_importances,
            "top_factors": self.top_factors,
        }

        joblib.dump(payload, filepath)
        return filepath

    @classmethod
    def load(cls, filepath: Optional[str] = None) -> "DeliveryDelayModel":
        """Deserialize and restore model + preprocessor package.

        Args:
            filepath: Path to saved artifact. Defaults to modules/delivery_delay/artifacts/delivery_delay_model_v1.joblib

        Returns:
            Restored DeliveryDelayModel instance.
        """
        if filepath is None:
            filepath = str(Path(__file__).parent / "artifacts" / "delivery_delay_model_v1.joblib")

        path = Path(filepath)
        if not path.is_file():
            raise FileNotFoundError(f"Model artifact not found at: {filepath}")

        payload = joblib.load(str(path))
        instance = cls(
            model_name=payload.get("model_name", "delivery-delay-model"),
            version=payload.get("version", "1.0"),
        )
        instance.estimator = payload["estimator"]
        instance.feature_pipeline = payload["feature_pipeline"]
        instance.feature_importances = payload.get("feature_importances", {})
        instance.top_factors = payload.get("top_factors", [])

        return instance
