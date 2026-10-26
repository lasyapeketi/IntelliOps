from pathlib import Path

import pandas as pd


# Resolve the CSV paths relative to this script so it works from any working directory.
DATA_DIR = Path(__file__).resolve().parents[2]
DATASETS = (
    "retail_store_inventory.csv",
    "ecommerce_demand_weekly.csv",
)

# Match common column-name variations without confusing stockout flags with
# inventory quantities.
COLUMN_ALIASES = {
    "date": {"date", "datetime", "timestamp", "week", "period"},
    "product identifier": {"productid", "product", "sku", "itemid"},
    "store identifier": {"storeid", "store", "locationid"},
    "sales": {"sales", "unitssold", "salesunits"},
    "demand": {"demand", "truedemand", "demandforecast"},
    "inventory": {
        "inventory",
        "inventorylevel",
        "stockonhand",
        "onhandinventory",
        "quantityinstock",
    },
}


def normalized_name(column_name):
    """Normalize a column label for case- and punctuation-insensitive matching."""
    return "".join(character.lower() for character in str(column_name) if character.isalnum())


def inspect_dataset(filename):
    """Print the requested data-quality and forecasting-relevant details."""
    path = DATA_DIR / filename
    dataframe = pd.read_csv(path)

    print(f"\n{'=' * 80}\nDataset: {filename}")
    print(f"Shape (rows, columns): {dataframe.shape}")

    print("\nColumns and data types:")
    for column_name, dtype in dataframe.dtypes.items():
        print(f"  {column_name}: {dtype}")

    print("\nFirst five rows:")
    print(dataframe.head().to_string(index=False))

    print("\nMissing values per column:")
    missing_counts = dataframe.isna().sum()
    for column_name, count in missing_counts.items():
        print(f"  {column_name}: {count}")
    print(f"Total missing values: {int(missing_counts.sum())}")

    duplicate_count = int(dataframe.duplicated().sum())
    print(f"\nDuplicate rows: {duplicate_count}")

    print("\nPossible forecasting columns:")
    normalized_columns = {
        column_name: normalized_name(column_name) for column_name in dataframe.columns
    }
    for role, aliases in COLUMN_ALIASES.items():
        matches = [
            column_name
            for column_name, normalized in normalized_columns.items()
            if normalized in aliases
        ]
        print(f"  {role}: {', '.join(matches) if matches else 'None found'}")

    date_columns = [
        column_name
        for column_name, normalized in normalized_columns.items()
        if normalized in COLUMN_ALIASES["date"]
    ]
    if date_columns:
        print("\nDate ranges:")
        for column_name in date_columns:
            parsed_dates = pd.to_datetime(dataframe[column_name], errors="coerce")
            valid_dates = parsed_dates.dropna()
            if valid_dates.empty:
                print(f"  {column_name}: no values could be parsed as dates")
            else:
                print(
                    f"  {column_name}: {valid_dates.min().date()} to "
                    f"{valid_dates.max().date()}"
                )
    else:
        print("\nDate ranges: no date columns found")


if __name__ == "__main__":
    for dataset in DATASETS:
        inspect_dataset(dataset)

    print(
        "\nForecasting suitability:\n"
        "- ecommerce_demand_weekly.csv is the stronger starting point for a weekly "
        "demand forecast: it has a weekly date sequence and an explicit true_demand "
        "target, along with SKU, sales, promotion, and stockout features.\n"
        "- retail_store_inventory.csv is useful for store/product-level inventory "
        "planning: it includes store and product identifiers, inventory levels, "
        "units sold, and a demand forecast. Its existing Demand Forecast column "
        "should not be used as an input when the goal is to predict demand, since "
        "that could leak forecast information into the model.\n"
        "- Keep the datasets separate unless a verified common key and compatible "
        "time grain and business definitions establish that joining them is valid."
    )
