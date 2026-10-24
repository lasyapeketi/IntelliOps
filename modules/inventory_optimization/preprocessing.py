
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INPUT_FILE = ROOT / "data" / "Online Retail.xlsx"
OUTPUT_FILE = ROOT / "data" / "processed" / "daily_demand.csv"

def prepare_daily_demand(input_file=INPUT_FILE, output_file=OUTPUT_FILE):
    if not input_file.exists():
        raise FileNotFoundError(f"Dataset not found: {input_file}")

    df = pd.read_excel(input_file, engine="openpyxl")

    required = {"InvoiceNo", "StockCode", "Quantity", "InvoiceDate"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    original_rows = len(df)
    df["InvoiceNo"] = df["InvoiceNo"].astype(str).str.strip()
    df["StockCode"] = df["StockCode"].astype("string").str.strip()
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")

    df = df.dropna(subset=["StockCode", "InvoiceDate", "Quantity"])
    df = df[df["StockCode"] != ""]
    df = df[~df["InvoiceNo"].str.upper().str.startswith("C")]
    df = df[df["Quantity"] > 0]

    if df.empty:
        raise ValueError("No valid sales transactions remain after cleaning.")

    df["Date"] = df["InvoiceDate"].dt.normalize()

    daily = (
        df.groupby(["StockCode", "Date"], as_index=False)["Quantity"]
        .sum()
        .rename(columns={"StockCode": "product_id", "Quantity": "daily_demand"})
    )

    calendar = pd.date_range(
        daily["Date"].min(), daily["Date"].max(), freq="D"
    )

    # Fill days without recorded sales with zero for each product.
    # This assumes the product was observable throughout the dataset period.
    result = []
    for product_id, group in daily.groupby("product_id", sort=False):
        series = group.set_index("Date")["daily_demand"].reindex(
            calendar, fill_value=0
        )
        result.append(
            pd.DataFrame({
                "Date": calendar,
                "product_id": product_id,
                "daily_demand": series.to_numpy()
            })
        )

    output = pd.concat(result, ignore_index=True)
    output["daily_demand"] = output["daily_demand"].astype(float)
    output = output.sort_values(["product_id", "Date"])

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_file, index=False)

    print(f"Original rows: {original_rows:,}")
    print(f"Valid transactions: {len(df):,}")
    print(f"Products: {output['product_id'].nunique():,}")
    print(f"Daily product records: {len(output):,}")
    print(f"Date range: {output['Date'].min().date()} to {output['Date'].max().date()}")
    print(f"Saved cleaned data to: {output_file}")
    print(output.head(10).to_string(index=False))

if __name__ == "__main__":
    prepare_daily_demand()
