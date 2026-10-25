"""Service Layer for Delivery Delay Prediction.

Loads model and preprocessor once into memory (singleton pattern).
Provides:
- predict(input_dict, include_explanation): returns label, value, confidence, and key_factors
- process_request(request_payload): returns standard IntelliOps JSON envelope
- Structured error handling naming missing or invalid fields without raw tracebacks
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from modules.delivery_delay.model import DeliveryDelayModel
from modules.delivery_delay.predict import predict_delivery_delay
from modules.delivery_delay.preprocessing import (
    ALLOWED_SHIPPING_METHODS,
    FORBIDDEN_LEAKAGE_COLUMNS,
    REQUIRED_INFERENCE_FIELDS,
)


class DeliveryDelayValidationError(ValueError):
    """Structured validation error indicating the exact invalid or missing field."""

    def __init__(self, field: str, message: str, code: str = "VALIDATION_ERROR") -> None:
        self.field = field
        self.message = message
        self.code = code
        super().__init__(f"Validation error on '{field}': {message}")

    def to_dict(self) -> Dict[str, str]:
        return {
            "code": self.code,
            "field": self.field,
            "message": self.message,
        }


class DeliveryDelayService:
    """Singleton service for delivery delay inference and response packaging."""

    _instance: Optional["DeliveryDelayService"] = None
    _cached_model: Optional[DeliveryDelayModel] = None

    def __new__(cls, *args, **kwargs) -> "DeliveryDelayService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, artifact_path: Optional[str] = None) -> None:
        """Initialize service and load model + preprocessor once."""
        if DeliveryDelayService._cached_model is None:
            self._load_model_once(artifact_path)

    @classmethod
    def _load_model_once(cls, artifact_path: Optional[str] = None) -> None:
        """Load the model and feature pipeline once into class memory."""
        if artifact_path is None:
            default_path = Path(__file__).parent / "artifacts" / "delivery_delay_model_v1.joblib"
            artifact_path = str(default_path)

        path = Path(artifact_path)
        if not path.is_file():
            # If artifact does not exist yet, train and save it automatically
            from modules.delivery_delay.train_model import run_full_training_and_comparison
            run_full_training_and_comparison()

        cls._cached_model = DeliveryDelayModel.load(str(path))
        print(f"[DeliveryDelayService] Model '{cls._cached_model.model_name}' (v{cls._cached_model.version}) loaded into memory.")

    @property
    def model(self) -> DeliveryDelayModel:
        """Return cached model instance."""
        if DeliveryDelayService._cached_model is None:
            self._load_model_once()
        return DeliveryDelayService._cached_model

    def validate_input(self, input_dict: Any) -> Dict[str, Any]:
        """Validate input feature dictionary and raise structured error naming the field.

        Args:
            input_dict: Raw input dictionary.

        Returns:
            Cleaned and typed input feature dictionary.

        Raises:
            DeliveryDelayValidationError: On any missing or invalid field.
        """
        if not isinstance(input_dict, dict):
            raise DeliveryDelayValidationError(
                field="input",
                message="Expected 'input' to be a JSON object / Python dictionary.",
            )

        # Anti-leakage verification
        for forbidden in FORBIDDEN_LEAKAGE_COLUMNS:
            if forbidden in input_dict:
                raise DeliveryDelayValidationError(
                    field=f"input.{forbidden}",
                    message="Anti-leakage violation: actual delivery data must never be provided as an input feature.",
                )

        # Check missing required fields
        for field in REQUIRED_INFERENCE_FIELDS:
            if field not in input_dict or input_dict[field] is None:
                raise DeliveryDelayValidationError(
                    field=f"input.{field}",
                    message=f"Missing required field '{field}'.",
                )

        # Validate distance_km
        try:
            distance_km = float(input_dict["distance_km"])
        except (ValueError, TypeError):
            raise DeliveryDelayValidationError(
                field="input.distance_km",
                message="Field 'distance_km' must be a valid numeric float.",
            )
        if distance_km <= 0:
            raise DeliveryDelayValidationError(
                field="input.distance_km",
                message="Field 'distance_km' must be a positive number greater than 0.",
            )

        # Validate shipping_method
        shipping_method = str(input_dict["shipping_method"]).strip().lower()
        if shipping_method not in ALLOWED_SHIPPING_METHODS:
            raise DeliveryDelayValidationError(
                field="input.shipping_method",
                message=f"Invalid shipping_method '{shipping_method}'. Allowed options: {sorted(list(ALLOWED_SHIPPING_METHODS))}.",
            )

        # Validate promised_delivery_days
        try:
            promised = int(input_dict["promised_delivery_days"])
        except (ValueError, TypeError):
            raise DeliveryDelayValidationError(
                field="input.promised_delivery_days",
                message="Field 'promised_delivery_days' must be a valid integer.",
            )
        if promised < 1:
            raise DeliveryDelayValidationError(
                field="input.promised_delivery_days",
                message="Field 'promised_delivery_days' must be an integer >= 1.",
            )

        # Validate historical_avg_delivery_days
        try:
            hist_avg = float(input_dict["historical_avg_delivery_days"])
        except (ValueError, TypeError):
            raise DeliveryDelayValidationError(
                field="input.historical_avg_delivery_days",
                message="Field 'historical_avg_delivery_days' must be a valid numeric float.",
            )
        if hist_avg <= 0:
            raise DeliveryDelayValidationError(
                field="input.historical_avg_delivery_days",
                message="Field 'historical_avg_delivery_days' must be a positive number greater than 0.",
            )

        # Validate order_volume
        try:
            order_volume = int(input_dict["order_volume"])
        except (ValueError, TypeError):
            raise DeliveryDelayValidationError(
                field="input.order_volume",
                message="Field 'order_volume' must be a valid integer.",
            )
        if order_volume < 1:
            raise DeliveryDelayValidationError(
                field="input.order_volume",
                message="Field 'order_volume' must be an integer >= 1.",
            )

        return {
            "distance_km": distance_km,
            "shipping_method": shipping_method,
            "promised_delivery_days": promised,
            "historical_avg_delivery_days": hist_avg,
            "order_volume": order_volume,
        }

    def predict(
        self,
        input_dict: Dict[str, Any],
        include_explanation: bool = True,
    ) -> Dict[str, Any]:
        """Perform inference on input features.

        Args:
            input_dict: Dictionary containing input features.
            include_explanation: If False, returns key_factors as [].

        Returns:
            Dict containing {"label", "value", "confidence", "key_factors"}.

        Raises:
            DeliveryDelayValidationError: Structured error naming any invalid field.
        """
        validated_input = self.validate_input(input_dict)
        pred, expl = predict_delivery_delay(
            model=self.model,
            input_data=validated_input,
            include_explanation=include_explanation,
        )

        return {
            "label": pred["label"],
            "value": pred["value"],
            "confidence": pred["confidence"],
            "key_factors": expl["key_factors"],
        }

    def process_request(self, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process full IntelliOps request envelope and return standard JSON response.

        Never crashes with a raw traceback; always returns structured errors.
        """
        request_id = request_payload.get("request_id") if isinstance(request_payload, dict) else None
        use_case = "delivery_delay"

        try:
            if not isinstance(request_payload, dict):
                raise DeliveryDelayValidationError(
                    field="request",
                    message="Request body must be a valid JSON object.",
                )

            # Check use_case
            req_use_case = request_payload.get("use_case")
            if req_use_case != use_case:
                raise DeliveryDelayValidationError(
                    field="use_case",
                    message=f"Invalid use_case '{req_use_case}'. Expected '{use_case}'.",
                )

            # Check input presence
            if "input" not in request_payload or request_payload["input"] is None:
                raise DeliveryDelayValidationError(
                    field="input",
                    message="Field 'input' is required.",
                )

            raw_input = request_payload["input"]
            options = request_payload.get("options", {}) or {}
            include_explanation = options.get("include_explanation", True)

            # Validate input features
            validated_input = self.validate_input(raw_input)

            # Predict
            pred, expl = predict_delivery_delay(
                model=self.model,
                input_data=validated_input,
                include_explanation=include_explanation,
            )

            return {
                "success": True,
                "use_case": use_case,
                "request_id": request_id,
                "prediction": pred,
                "explanation": expl,
                "model": {
                    "name": self.model.model_name,
                    "version": self.model.version,
                },
                "errors": [],
            }

        except DeliveryDelayValidationError as err:
            return {
                "success": False,
                "use_case": use_case,
                "request_id": request_id,
                "prediction": None,
                "explanation": None,
                "model": None,
                "errors": [err.to_dict()],
            }
        except Exception as exc:
            # Shield internal tracebacks from callers
            return {
                "success": False,
                "use_case": use_case,
                "request_id": request_id,
                "prediction": None,
                "explanation": None,
                "model": None,
                "errors": [
                    {
                        "code": "INTERNAL_SERVER_ERROR",
                        "field": None,
                        "message": "An unexpected error occurred while processing the request.",
                    }
                ],
            }
