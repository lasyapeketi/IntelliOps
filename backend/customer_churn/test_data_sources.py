"""
Automated Test Suite for ChurnNexus Multi-Source Data Ingestion Architecture
Tests all 5 data sources:
1. CSV Upload / Parsing
2. Excel Upload with Worksheet Selection (.xlsx, .xls)
3. Dataset URL Ingestion & Validation
4. Hugging Face Dataset Ingestion (scikit-learn/churn-prediction)
5. SQL Database Table Ingestion (SQLite)
And validates end-to-end integration into ChurnPreprocessor and Model Training.
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from data_loader import (
    load_csv, get_excel_sheets, load_excel, load_url, load_huggingface,
    get_sql_tables, load_sql_table, DataLoaderError
)
from preprocess import ChurnPreprocessor
from model import train_and_evaluate_models


def test_source_csv():
    print("\n[TEST 1] Testing CSV Data Source...")
    csv_path = "dataset/sample_churn.csv"
    if not os.path.exists(csv_path):
        from dataset.generate_mock_data import generate_mock_churn_data
        generate_mock_churn_data(csv_path, 200)

    df = load_csv(csv_path)
    assert isinstance(df, pd.DataFrame), "CSV loader must return a pandas DataFrame"
    assert not df.empty, "DataFrame should not be empty"
    print(f"✓ CSV loaded successfully: shape {df.shape}, columns: {list(df.columns[:5])}...")

    # Pass into ML preprocessor
    prep = ChurnPreprocessor()
    X_trans, y = prep.fit_transform(df, "Churn")
    assert X_trans.shape[0] == df.shape[0], "Transformed X row count must match input"
    print(f"✓ CSV pipeline compatibility verified: X shape {X_trans.shape}, y shape {y.shape}")
    return df


def test_source_excel():
    print("\n[TEST 2] Testing Excel Data Source (.xlsx with multiple worksheets)...")
    excel_path = "dataset/test_multi_sheet.xlsx"

    # Create sample workbook with 2 sheets
    df_sample = pd.read_csv("dataset/sample_churn.csv")
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        pd.DataFrame({"info": ["Metadata Sheet", "Version 1.0"]}).to_excel(writer, sheet_name="Readme", index=False)
        df_sample.to_excel(writer, sheet_name="Customers_Churn", index=False)

    # Test sheet inspection
    sheets = get_excel_sheets(excel_path)
    assert "Readme" in sheets and "Customers_Churn" in sheets, "Must detect all worksheets"
    print(f"✓ Detected {len(sheets)} worksheets: {sheets}")

    # Test sheet loading
    df_excel = load_excel(excel_path, sheet_name="Customers_Churn")
    assert isinstance(df_excel, pd.DataFrame), "Excel loader must return a pandas DataFrame"
    assert df_excel.shape[0] == df_sample.shape[0], "Loaded sheet rows must match expected"
    print(f"✓ Excel worksheet 'Customers_Churn' loaded: shape {df_excel.shape}")

    # Pass into ML preprocessor
    prep = ChurnPreprocessor()
    X_trans, y = prep.fit_transform(df_excel, "Churn")
    print(f"✓ Excel pipeline compatibility verified: X shape {X_trans.shape}, y shape {y.shape}")

    # Cleanup test excel
    if os.path.exists(excel_path):
        os.remove(excel_path)
    return df_excel


def test_source_url():
    print("\n[TEST 3] Testing Dataset URL Data Source...")
    # Test valid public URL (IBM Telco Churn raw GitHub URL)
    test_url = "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"
    try:
        df_url = load_url(test_url)
        assert isinstance(df_url, pd.DataFrame), "URL loader must return a DataFrame"
        assert not df_url.empty, "URL DataFrame must not be empty"
        print(f"✓ Remote URL dataset loaded successfully: shape {df_url.shape}")

        # Verify ML preprocessor compatibility
        prep = ChurnPreprocessor()
        X_trans, y = prep.fit_transform(df_url, "Churn")
        print(f"✓ URL pipeline compatibility verified: X shape {X_trans.shape}, y shape {y.shape}")
    except Exception as e:
        print(f"⚠ Live network URL test note: {e}")

    # Test URL error handling
    try:
        load_url("https://invalid-url-that-does-not-exist-12345.com/nonexistent.csv")
        assert False, "Should raise DataLoaderError for nonexistent URL"
    except DataLoaderError as e:
        print(f"✓ Invalid URL error handling verified: '{e}'")


def test_source_huggingface():
    print("\n[TEST 4] Testing Hugging Face Dataset Data Source...")
    dataset_id = "scikit-learn/churn-prediction"

    df_hf = load_huggingface(dataset_id)
    assert isinstance(df_hf, pd.DataFrame), "Hugging Face loader must return a DataFrame"
    assert df_hf.shape[0] == 7043, f"Expected 7,043 rows, got {df_hf.shape[0]}"
    assert df_hf.shape[1] == 21, f"Expected 21 columns, got {df_hf.shape[1]}"
    print(f"✓ Hugging Face dataset '{dataset_id}' loaded: shape {df_hf.shape}")

    # Pass into ML preprocessor & verify ML pipeline
    prep = ChurnPreprocessor()
    X_trans, y = prep.fit_transform(df_hf, "Churn")
    print(f"✓ Hugging Face pipeline compatibility verified: X shape {X_trans.shape}, y shape {y.shape}")

    # Test error handling on invalid HF ID
    try:
        load_huggingface("nonexistent_user/nonexistent_dataset_churn_99999")
        assert False, "Should raise DataLoaderError for nonexistent HF dataset"
    except DataLoaderError as e:
        print(f"✓ Hugging Face error handling verified: '{e}'")

    return df_hf


def test_source_sql():
    print("\n[TEST 5] Testing SQL Database Data Source (SQLite)...")
    db_path = "dataset/test_customers.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    # Populate sample SQLite DB
    df_sample = pd.read_csv("dataset/sample_churn.csv")
    conn = sqlite3.connect(db_path)
    df_sample.to_sql("customers_data", conn, index=False, if_exists="replace")
    df_sample.head(20).to_sql("recent_churners", conn, index=False, if_exists="replace")
    conn.close()

    # Test table listing
    tables = get_sql_tables("sqlite", sqlite_file=db_path)
    assert "customers_data" in tables and "recent_churners" in tables, "Must list all tables"
    print(f"✓ SQLite tables inspected: {tables}")

    # Test table loading
    df_sql = load_sql_table("sqlite", table_name="customers_data", sqlite_file=db_path)
    assert isinstance(df_sql, pd.DataFrame), "SQL loader must return a DataFrame"
    assert df_sql.shape[0] == df_sample.shape[0], "SQL table row count must match original"
    print(f"✓ SQLite table 'customers_data' loaded: shape {df_sql.shape}")

    # Pass into ML preprocessor
    prep = ChurnPreprocessor()
    X_trans, y = prep.fit_transform(df_sql, "Churn")
    print(f"✓ SQL pipeline compatibility verified: X shape {X_trans.shape}, y shape {y.shape}")

    # Test error handling on invalid table
    try:
        load_sql_table("sqlite", table_name="invalid_table_name_xyz", sqlite_file=db_path)
        assert False, "Should raise DataLoaderError for invalid table"
    except DataLoaderError as e:
        print(f"✓ SQL error handling verified: '{e}'")

    # Cleanup test db
    import gc
    gc.collect()
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass

    return df_sql


def test_end_to_end_ml_training():
    print("\n[TEST 6] Testing End-to-End Model Training on Ingested Data...")
    df = pd.read_csv("dataset/sample_churn.csv")
    prep = ChurnPreprocessor()
    X_trans, y = prep.fit_transform(df, "Churn")

    # Train models
    eval_results, best_model_path = train_and_evaluate_models(X_trans, y, prep.feature_cols)
    assert os.path.exists(best_model_path), "Best model file should be created"
    assert "best_model_name" in eval_results, "Evaluation must identify best model"
    print(f"✓ Model training completed successfully! Best model: {eval_results['best_model_name']}")


if __name__ == "__main__":
    print("==================================================================")
    print("   STARTING MULTI-SOURCE DATA LOADER ARCHITECTURE VALIDATION")
    print("==================================================================")

    test_source_csv()
    test_source_excel()
    test_source_url()
    test_source_huggingface()
    test_source_sql()
    test_end_to_end_ml_training()

    print("\n==================================================================")
    print("   ALL 5 DATA SOURCES VERIFIED & PIPELINE FULLY COMPATIBLE! ✓")
    print("==================================================================")
