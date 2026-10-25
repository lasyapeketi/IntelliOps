import os
import numpy as np
import pandas as pd

def generate_mock_churn_data(file_path, num_samples=1000):
    np.random.seed(42)

    # Generate Customer IDs
    customer_ids = [f"{np.random.randint(1000, 9999)}-{np.random.choice(list('ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 5)}" for _ in range(num_samples)]

    # Generate demographic and service variables
    gender = np.random.choice(["Male", "Female"], size=num_samples)
    senior_citizen = np.random.choice([0, 1], size=num_samples, p=[0.85, 0.15])
    partner = np.random.choice(["Yes", "No"], size=num_samples)
    dependents = np.random.choice(["Yes", "No"], size=num_samples, p=[0.7, 0.3])

    # Tenure in months
    tenure = np.random.randint(1, 73, size=num_samples)

    phone_service = np.random.choice(["Yes", "No"], size=num_samples, p=[0.9, 0.1])

    multiple_lines = []
    for p in phone_service:
        if p == "No":
            multiple_lines.append("No phone service")
        else:
            multiple_lines.append(np.random.choice(["Yes", "No"]))

    internet_service = np.random.choice(["DSL", "Fiber optic", "No"], size=num_samples, p=[0.3, 0.5, 0.2])

    online_security = []
    online_backup = []
    device_protection = []
    tech_support = []
    streaming_tv = []
    streaming_movies = []

    for i in internet_service:
        if i == "No":
            online_security.append("No internet service")
            online_backup.append("No internet service")
            device_protection.append("No internet service")
            tech_support.append("No internet service")
            streaming_tv.append("No internet service")
            streaming_movies.append("No internet service")
        else:
            online_security.append(np.random.choice(["Yes", "No"], p=[0.4, 0.6]))
            online_backup.append(np.random.choice(["Yes", "No"], p=[0.45, 0.55]))
            device_protection.append(np.random.choice(["Yes", "No"], p=[0.45, 0.55]))
            tech_support.append(np.random.choice(["Yes", "No"], p=[0.4, 0.6]))
            streaming_tv.append(np.random.choice(["Yes", "No"], p=[0.5, 0.5]))
            streaming_movies.append(np.random.choice(["Yes", "No"], p=[0.5, 0.5]))

    contract = np.random.choice(["Month-to-month", "One year", "Two year"], size=num_samples, p=[0.55, 0.20, 0.25])
    paperless_billing = np.random.choice(["Yes", "No"], size=num_samples, p=[0.6, 0.4])
    payment_method = np.random.choice(
        ["Electronic check", "Mailed check", "Bank transfer (automatic)", "Credit card (automatic)"],
        size=num_samples,
        p=[0.35, 0.25, 0.20, 0.20]
    )

    # Calculate Monthly Charges based on internet service and features
    monthly_charges = []
    for idx, i in enumerate(internet_service):
        charge = 20.0  # Base charge
        if i == "DSL":
            charge += 30.0
        elif i == "Fiber optic":
            charge += 50.0

        if phone_service[idx] == "Yes":
            charge += 10.0
        if multiple_lines[idx] == "Yes":
            charge += 5.0
        if online_security[idx] == "Yes":
            charge += 5.0
        if online_backup[idx] == "Yes":
            charge += 5.0
        if device_protection[idx] == "Yes":
            charge += 5.0
        if tech_support[idx] == "Yes":
            charge += 5.0
        if streaming_tv[idx] == "Yes":
            charge += 8.0
        if streaming_movies[idx] == "Yes":
            charge += 8.0

        # Add some random noise
        charge += np.random.normal(0, 3)
        monthly_charges.append(round(max(15.0, charge), 2))

    monthly_charges = np.array(monthly_charges)

    # Calculate Total Charges (Tenure * MonthlyCharges)
    total_charges = []
    for idx, t in enumerate(tenure):
        total = t * monthly_charges[idx]
        total_charges.append(round(total, 2))

    # Introduce some random missing values in TotalCharges to test cleaner
    total_charges = [str(tc) if np.random.rand() > 0.01 else " " for tc in total_charges]

    # Churn probability based on risk factors:
    # High monthly charges, short tenure, Month-to-month contract, Fiber optic, No OnlineSecurity/TechSupport
    churn_prob = []
    for idx in range(num_samples):
        prob = 0.1  # Base probability

        # Tenure effect (longer tenure = less churn)
        t = tenure[idx]
        prob += 0.4 * (1.0 - min(t, 24) / 24.0)  # High risk for first 2 years

        # Contract effect
        c = contract[idx]
        if c == "Month-to-month":
            prob += 0.3
        elif c == "One year":
            prob -= 0.1
        elif c == "Two year":
            prob -= 0.2

        # Internet Service / Features
        i = internet_service[idx]
        if i == "Fiber optic":
            prob += 0.15

        if online_security[idx] == "No":
            prob += 0.08
        if tech_support[idx] == "No":
            prob += 0.08

        # Payment Method
        if payment_method[idx] == "Electronic check":
            prob += 0.1

        # Monthly Charges (higher charges = more churn)
        mc = monthly_charges[idx]
        prob += 0.15 * (mc - 20.0) / 100.0

        # Keep probability in [0.02, 0.98]
        prob = max(0.02, min(0.98, prob))
        churn_prob.append(prob)

    churn = []
    for p in churn_prob:
        churn.append("Yes" if np.random.rand() < p else "No")

    df = pd.DataFrame({
        "customerID": customer_ids,
        "gender": gender,
        "SeniorCitizen": senior_citizen,
        "Partner": partner,
        "Dependents": dependents,
        "tenure": tenure,
        "PhoneService": phone_service,
        "MultipleLines": multiple_lines,
        "InternetService": internet_service,
        "OnlineSecurity": online_security,
        "OnlineBackup": online_backup,
        "DeviceProtection": device_protection,
        "TechSupport": tech_support,
        "StreamingTV": streaming_tv,
        "StreamingMovies": streaming_movies,
        "Contract": contract,
        "PaperlessBilling": paperless_billing,
        "PaymentMethod": payment_method,
        "MonthlyCharges": monthly_charges,
        "TotalCharges": total_charges,
        "Churn": churn
    })

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    df.to_csv(file_path, index=False)
    print(f"Mock churn data generated at: {file_path}")

if __name__ == "__main__":
    generate_mock_churn_data("dataset/sample_churn.csv", 1000)
