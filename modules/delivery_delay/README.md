# Delivery Delay Prediction Module (`delivery_delay`)

## 1. Overview
The **Delivery Delay Prediction** module provides real-time inference and decision support for logistics and supply-chain operations. It predicts whether a customer shipment is at risk of being delayed before transit completes, allowing operations teams to intervene proactively.

---

## 2. API Contract & Specification

- **Module Identifier (`use_case`):** `delivery_delay`
- **HTTP Method & Route:** `POST /api/v1/predict/delivery_delay`
- **Content-Type:** `application/json`

---

## 3. Target Definition & Data Leakage Prevention Rule

### Target Variable: `delayed`
- **Definition:** Binary classification target.
  - `1` (`delayed`): `actual_delivery_days > promised_delivery_days`
  - `0` (`on_time`): `actual_delivery_days <= promised_delivery_days`

### ⚠️ Strict Anti-Leakage Rule
- **Actual delivery date, actual delivery time, and actual transit duration must NEVER be used as input features.**
- Only information strictly known **at or before dispatch / order scheduling time** may be provided in inference requests or used during model training.

---

## 4. Input Schema & Field Definitions

All input fields are submitted inside the `input` object of the standard request envelope.

| Field Name | Type | Unit | Allowed Values / Constraints | Missing Value / Error Behavior | Description |
|---|---|---|---|---|---|
| `distance_km` | `float` | Kilometers (km) | `> 0.0` (e.g., `0.1` to `20000.0`) | **Required**. Returns HTTP 422 validation error if missing or non-positive. | Distance between origin warehouse and destination address. |
| `shipping_method` | `string` | Categorical | `"standard"`, `"express"`, `"same_day"`, `"overnight"` | **Required**. Returns HTTP 422 validation error if missing or not an allowed string. | Logistics service level tier selected for the shipment. |
| `promised_delivery_days` | `integer` | Days | `integer >= 1` | **Required**. Returns HTTP 422 validation error if missing or `< 1`. | Number of days promised to the customer for order delivery. |
| `historical_avg_delivery_days` | `float` | Days | `> 0.0` | **Required**. Returns HTTP 422 validation error if missing or `<= 0.0`. | Historical average transit duration (in days) on this route/carrier. |
| `order_volume` | `integer` | Units / Packages | `integer >= 1` | **Required**. Returns HTTP 422 validation error if missing or `< 1`. | Number of items or package volume associated with this consignment. |

---

## 5. Standard Request Format

```json
{
  "use_case": "delivery_delay",
  "request_id": "req-delivery-1001",
  "input": {
    "distance_km": 420.5,
    "shipping_method": "standard",
    "promised_delivery_days": 3,
    "historical_avg_delivery_days": 3.8,
    "order_volume": 4
  },
  "options": {
    "include_explanation": true
  }
}
```

---

## 6. Standard Successful Response Format

Conforms exactly to the IntelliOps shared response contract (`docs/docs/api-contracts.md`):

```json
{
  "success": true,
  "use_case": "delivery_delay",
  "request_id": "req-delivery-1001",
  "prediction": {
    "label": "delayed",
    "value": 1,
    "confidence": 0.84
  },
  "explanation": {
    "summary": "Shipment has an 84% probability of delay because historical average delivery time (3.8 days) exceeds the promised delivery window (3 days).",
    "key_factors": [
      "Historical route average (3.8 days) exceeds promised SLA (3 days)",
      "Standard shipping method selected over high distance (420.5 km)"
    ]
  },
  "model": {
    "name": "delivery-delay-classifier",
    "version": "1.0.0"
  },
  "errors": []
}
```

### Output Field Descriptions
- `prediction.label`: `"delayed"` or `"on_time"`
- `prediction.value`: `1` (delayed) or `0` (on_time)
- `prediction.confidence`: Float `[0.0, 1.0]` representing the predicted class probability
- `explanation.summary`: Human-readable summary for decision makers
- `explanation.key_factors`: List of dominant feature contributors
- `model.name`: Identifier of the loaded model artifact
- `model.version`: Semantic version of the trained model

---

## 7. Standard Error Response Format

```json
{
  "success": false,
  "use_case": "delivery_delay",
  "request_id": "req-delivery-1001",
  "prediction": null,
  "explanation": null,
  "model": null,
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "field": "input.distance_km",
      "message": "distance_km must be a positive number greater than 0"
    }
  ]
}
```

---

## 8. Differences & Alignment with `docs/docs/api-contracts.md`

1. **Route Convention & Aliasing:**
   - **Canonical Route:** `POST /api/v1/predict/delivery_delay` (standardized as per `docs/docs/api-contracts.md` Section 7).
   - **Supported Alias:** `POST /api/v1/delivery-delay/predict` (supported for compatibility with Section 6.1 example).
   - *Note for PR Reviewer:* The canonical contract is `/api/v1/predict/delivery_delay`. Both routes are fully functional and return identical envelopes. Please confirm during PR review whether the alias route should remain or be removed.
2. **Input Fields:**
   - `docs/docs/api-contracts.md` listed placeholder fields (`feature_1`, `feature_2`, `feature_3`) and stated that each use case must define its concrete fields. This document locks the concrete fields: `distance_km`, `shipping_method`, `promised_delivery_days`, `historical_avg_delivery_days`, and `order_volume`.
3. **Response Envelope:**
   - Fully aligned with top-level keys: `success`, `use_case`, `request_id`, `prediction`, `explanation`, `model`, and `errors`.

---

## 9. Dataset Documentation (Synthetic Sample)

- **Dataset File:** `modules/delivery_delay/data/synthetic_delivery_delay.csv`
- **Data Status:** **SYNTHETIC DATA**. This dataset is artificially generated for training, benchmarking, unit testing, and prototype validation in the absence of proprietary logistics records.
- **Record Count:** 65 rows (60 valid training/testing samples, 5 intentional validation test cases with invalid/missing values).
- **Target Generation:** `delayed = 1` if `actual_delivery_days > promised_delivery_days` else `0`.
- **Anti-Leakage Guarantee:** `actual_delivery_days` is strictly quarantined and used solely for target label computation. It is never included in the feature input space for training or real-time inference.

---

## 10. Baseline Model Evaluation (Preliminary Benchmarks)

> **Important Note:** These are preliminary baseline evaluations (Majority-Class Dummy and Logistic Regression) established to define a lower performance bound. **Neither baseline is claimed as the final production model.** Advanced candidate models (e.g., Random Forest, Gradient Boosting) will be evaluated against these baselines in subsequent stages.

### Test Split Protocol
- **Split Type:** Stratified 75% Train / 25% Test split (`random_state=42`)
- **Total Samples:** 60 clean records (31 Delayed, 29 On-Time)
- **Train Split:** 45 samples (23 Delayed, 22 On-Time)
- **Test Split:** 15 samples (8 Delayed, 7 On-Time)
- **Preprocessing:** Fitted exclusively on the 45 training samples; applied to test split without refitting.

### Baseline Benchmark Results

| Metric | Majority-Class Baseline | Logistic Regression Baseline |
|---|---|---|
| **Accuracy** | 0.5333 | 0.8667 |
| **Precision (Delayed)** | 0.5333 | 0.8750 |
| **Recall (Delayed)** | 1.0000 | 0.8750 |
| **F1-Score** | 0.6957 | 0.8750 |
| **ROC-AUC** | 0.5000 | 0.9643 |
| **Confusion Matrix** | TN=0, FP=7, FN=0, TP=8 | TN=6, FP=1, FN=1, TP=7 |

---

## 11. Main Model: Random Forest Classifier (v1.0)

- **Artifact Name:** `delivery-delay-model`
- **Version:** `1.0`
- **Serialized Location:** `modules/delivery_delay/artifacts/delivery_delay_model_v1.joblib` (bundles the trained `RandomForestClassifier` and the pre-fitted `DeliveryDelayFeaturePipeline` together).

### Comparative Evaluation (Held-Out Test Set)

| Metric | Majority Class Baseline | Logistic Regression Baseline | **Random Forest Classifier (v1.0)** |
|---|---|---|---|
| **Accuracy** | 0.5333 | 0.8667 | **0.8667** |
| **Precision (Delayed)** | 0.5333 | **0.8750** | 0.8000 |
| **Recall (Delayed)** | 1.0000 | 0.8750 | **1.0000** |
| **F1-Score** | 0.6957 | 0.8750 | **0.8889** |
| **ROC-AUC** | 0.5000 | 0.9643 | **0.9821** |

### Confusion Matrix Comparison
- **Majority Class:** $\text{TN}=0, \text{FP}=7, \text{FN}=0, \text{TP}=8$
- **Logistic Regression:** $\text{TN}=6, \text{FP}=1, \text{FN}=1, \text{TP}=7$
- **Random Forest (v1.0):** $\text{TN}=5, \text{FP}=2, \mathbf{FN=0}, \mathbf{TP=8}$
  - *Operational advantage:* The Random Forest achieves **zero false negatives (FN=0)** on the test partition, ensuring that no delayed shipments are missed by logistics operations.

### Top 5 Important Features
The tree-based feature importances extracted from the model:

| Rank | Feature | Importance | Relative Impact |
|---|---|---|---|
| 1 | `order_volume` | 0.2559 | 25.6% |
| 2 | `historical_delay_ratio` | 0.2400 | 24.0% |
| 3 | `distance_km` | 0.1956 | 19.6% |
| 4 | `distance_per_promised_day` | 0.1511 | 15.1% |
| 5 | `historical_avg_delivery_days` | 0.0950 | 9.5% |

### Model Limitations
1. **Synthetic Data Calibration:** The current weights reflect synthetic training distributions; real-world carrier routing data should be ingested to retrain before large-scale commercial deployment.
2. **Unobserved External Factors:** Severe unexpected weather phenomena, port strikes, and carrier dispatch outages are not present in standard order-time attributes.
3. **Threshold Calibration:** At default classification threshold (0.5), the model prioritizes high recall ($\text{FN}=0$), resulting in slightly higher false alarms ($\text{FP}=2$). Threshold tuning can adjust this tradeoff based on operational tolerance.

---

## 12. Running the Module & Verification

### 1. Run Unit & Integration Tests
```powershell
python -m pytest modules/delivery_delay/tests/ -v
```

### 2. Start Backend API Server
```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
- **Interactive Swagger Docs:** `http://127.0.0.1:8000/docs`
- **OpenAPI Schema:** `http://127.0.0.1:8000/openapi.json`
- **Health Check:** `GET http://127.0.0.1:8000/health`
- **Prediction Endpoint:** `POST http://127.0.0.1:8000/api/v1/predict/delivery_delay`
