"""Inference Engine for Delivery Delay Prediction.

Calculates prediction class, calibrated confidence scores, and dynamic
explanatory factors from feature inputs and model weights.
"""

from typing import Any, Dict, List, Tuple
import pandas as pd
from modules.delivery_delay.model import DeliveryDelayModel


def generate_explanation(
    input_data: Dict[str, Any],
    prediction_value: int,
    confidence: float,
) -> Dict[str, Any]:
    """Generate business-oriented summary and key factors for the prediction.

    Args:
        input_data: Validated input feature dictionary.
        prediction_value: 1 for delayed, 0 for on_time.
        confidence: Predicted class probability.

    Returns:
        Dictionary with 'summary' and 'key_factors'.
    """
    factors: List[str] = []
    dist = input_data["distance_km"]
    method = input_data["shipping_method"]
    promised = input_data["promised_delivery_days"]
    hist_avg = input_data["historical_avg_delivery_days"]
    vol = input_data["order_volume"]

    hist_ratio = hist_avg / max(promised, 0.001)
    km_per_day = dist / max(promised, 0.001)

    if prediction_value == 1:
        # Delayed factors
        if hist_avg > promised:
            factors.append(
                f"Historical route average ({hist_avg:.1f} days) exceeds promised SLA ({promised} days) by {(hist_avg - promised):.1f} days."
            )
        elif hist_ratio >= 0.85:
            factors.append(
                f"Historical transit time ({hist_avg:.1f} days) leaves minimal safety margin under promised SLA ({promised} days)."
            )

        if km_per_day > 250:
            factors.append(
                f"High transit distance ({dist:.1f} km over {promised} promised day(s) = {km_per_day:.0f} km/day) increases transit vulnerability."
            )

        if vol >= 5:
            factors.append(
                f"High order volume ({vol} packages) creates potential warehouse sorting and palletizing bottlenecks."
            )

        if method == "standard" and dist > 400:
            factors.append(
                f"Standard shipping tier selected over extended distance ({dist:.1f} km) without priority dispatch."
            )

        if not factors:
            factors.append("Combined transit metrics and consignment attributes indicate elevated delay probability.")

        summary = (
            f"Shipment is predicted to be DELAYED with {confidence * 100:.1f}% confidence. "
            f"Primary driver is route duration relative to promised delivery timeline."
        )

    else:
        # On-time factors
        if hist_avg < promised:
            factors.append(
                f"Historical route transit ({hist_avg:.1f} days) is comfortably within promised delivery window ({promised} days)."
            )

        if method in ("same_day", "express", "overnight"):
            factors.append(
                f"Priority shipping tier ('{method}') ensures expedited carrier handling and accelerated dispatch."
            )

        if km_per_day <= 200:
            factors.append(
                f"Manageable transit rate ({km_per_day:.0f} km/day) allows ample buffer for route completion."
            )

        if vol <= 3:
            factors.append(
                f"Standard consignment size ({vol} package(s)) enables rapid hub throughput."
            )

        if not factors:
            factors.append("All operational indicators fall within normal on-time delivery parameters.")

        summary = (
            f"Shipment is predicted to arrive ON TIME with {confidence * 100:.1f}% confidence."
        )

    return {
        "summary": summary,
        "key_factors": factors,
    }


def predict_delivery_delay(
    model: DeliveryDelayModel,
    input_data: Dict[str, Any],
    include_explanation: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Generate delivery delay prediction and optional explanation.

    Args:
        model: Loaded DeliveryDelayModel instance.
        input_data: Validated dictionary of input features.
        include_explanation: If False, key_factors is returned as [].

    Returns:
        Tuple of (prediction_dict, explanation_dict).
    """
    # Create single-row DataFrame for pipeline transformation
    input_df = pd.DataFrame([input_data])

    # Transform through pre-fitted feature pipeline (no refitting)
    X_trans = model.feature_pipeline.transform(input_df)

    # Predict class probability
    probabilities = model.predict_proba(X_trans)[0]
    prob_delayed = float(probabilities[1])
    prob_ontime = float(probabilities[0])

    if prob_delayed >= 0.5:
        label = "delayed"
        value = 1
        confidence = round(prob_delayed, 4)
    else:
        label = "on_time"
        value = 0
        confidence = round(prob_ontime, 4)

    prediction = {
        "label": label,
        "value": value,
        "confidence": confidence,
    }

    if include_explanation:
        explanation = generate_explanation(input_data, value, confidence)
    else:
        explanation = {
            "summary": f"Shipment is predicted to be {label} with {confidence * 100:.1f}% confidence.",
            "key_factors": [],
        }

    return prediction, explanation
