from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "artifacts"
DATASET_PATH = DATA_DIR / "WA_Fn-UseC_-HR-Employee-Attrition.csv"
MODEL_PATH = MODEL_DIR / "attrition_pipeline.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"

# Demonstration threshold only. Tune using validation data and business needs.
RISK_THRESHOLD = 0.40
