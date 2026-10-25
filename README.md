# Employee Attrition Prediction

A standalone prototype built with React + Vite, FastAPI, Pandas, and scikit-learn.

## What it does
- Trains a classification model from the public IBM HR Analytics Employee Attrition dataset.
- Shows dataset/model metrics and feature importance.
- Uploads CSV files for batch attrition-risk estimates.
- Exports predictions as CSV.
- Provides a single-employee prediction form using a small set of supported fields.

> The dataset is fictional and for educational use. Predictions are estimates, not facts about an employee. Do not use this prototype to penalize employees or make automated employment decisions.

## 1. Requirements
- Python 3.10 or 3.11 recommended
- Node.js 20.19+ or 22.12+
- Internet connection for installing dependencies
- IBM HR Analytics CSV downloaded from Kaggle

Dataset page:
https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset

Download the CSV named `WA_Fn-UseC_-HR-Employee-Attrition.csv` and put it in:
`backend/data/WA_Fn-UseC_-HR-Employee-Attrition.csv`

Do not commit the raw dataset to a public repository without checking the source's current terms.

## 2. Start the backend (Windows PowerShell)
Open a terminal in the project folder:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python train_model.py
uvicorn app.main:app --reload
```

If PowerShell blocks activation, use Command Prompt and run:
```bat
.venv\Scripts\activate.bat
```

API: http://127.0.0.1:8000  
Interactive API docs: http://127.0.0.1:8000/docs

## 3. Start the React frontend
Open a second terminal at the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, usually http://localhost:5173.

## 4. Main API endpoints
- `GET /api/health` — backend/model status
- `GET /api/summary` — dataset and held-out test metrics
- `GET /api/features` — supported fields for single predictions
- `POST /api/predict` — predict one employee from JSON
- `POST /api/predict-batch` — upload a CSV and receive predictions

Batch CSV must contain the model input columns listed in `/api/features`. If it is the original dataset, `Attrition` can be present and will be ignored. The CSV should not include personal names or direct identifiers.

## 5. Model notes
- Uses a stratified train/test split and a scikit-learn pipeline.
- Excludes `Attrition` from model inputs and excludes direct identifiers and selected demographic fields (`EmployeeNumber`, `EmployeeCount`, `Over18`, `StandardHours`, `Age`, `Gender`, `MaritalStatus`) from features.
- Reports accuracy, precision, recall, F1, ROC-AUC, and a confusion matrix.
- Threshold is configurable in `backend/app/config.py`; default 0.40 is illustrative and should be tuned on validation data.
- Feature importance is model-based and does not prove causation.
- Because the dataset is cross-sectional and contains no dates, this project does not predict a specific departure date or monthly trend.

## 6. Troubleshooting
- `Dataset not found`: check the exact CSV filename and `backend/data/` path.
- `Model not found`: run `python train_model.py` from the `backend` folder.
- CORS/network errors: keep the backend on port 8000 and frontend on port 5173.
- If npm or Python packages fail, check the installed Node/Python versions.
