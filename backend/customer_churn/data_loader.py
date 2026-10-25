"""
ChurnNexus Unified Data Loading Layer
Provides unified data loading for:
- CSV Uploads
- Excel Uploads (.xlsx, .xls) with worksheet detection & selection
- Public Tabular Dataset URLs (CSV, Excel)
- Hugging Face Datasets via the `datasets` library
- SQL Databases (SQLite, MySQL, PostgreSQL)

Every loader returns a pandas.DataFrame.
Errors are mapped to user-friendly messages without exposing raw stack traces.
"""

import os
import io
import re
import sqlite3
import urllib.parse
import pandas as pd
import requests

# Suppress Hugging Face Windows symlink warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

class DataLoaderError(Exception):
    """Custom exception for user-friendly data loader errors."""
    pass


def load_csv(file_or_path):
    """
    Loads CSV from a file path, file-like object, or bytes.
    Returns: pandas.DataFrame
    """
    try:
        if isinstance(file_or_path, (str, os.PathLike)):
            try:
                df = pd.read_csv(file_or_path, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(file_or_path, encoding="latin1")
        else:
            # File-like object (e.g. from Flask request.files)
            try:
                df = pd.read_csv(file_or_path, encoding="utf-8")
            except UnicodeDecodeError:
                file_or_path.seek(0)
                df = pd.read_csv(file_or_path, encoding="latin1")

        if df.empty:
            raise DataLoaderError("The uploaded CSV file is empty.")
        return df

    except DataLoaderError:
        raise
    except Exception as e:
        raise DataLoaderError(f"❌ Could not load the dataset. Please check the file format or URL. ({str(e)})")


def get_excel_sheets(file_or_path):
    """
    Returns list of worksheet names from an Excel file (.xlsx or .xls).
    """
    try:
        xl = pd.ExcelFile(file_or_path)
        return xl.sheet_names
    except Exception as e:
        raise DataLoaderError(f"❌ Could not load the Excel file. Please check the file format (.xlsx or .xls).")


def load_excel(file_or_path, sheet_name=None):
    """
    Loads a sheet from an Excel file into a pandas DataFrame.
    If sheet_name is None, loads the first sheet.
    """
    try:
        sheet = sheet_name if sheet_name else 0
        df = pd.read_excel(file_or_path, sheet_name=sheet)

        if df.empty:
            raise DataLoaderError("The selected worksheet is empty.")
        return df

    except DataLoaderError:
        raise
    except Exception as e:
        raise DataLoaderError(f"❌ Could not load the dataset. Please check the file format or URL. ({str(e)})")


def load_url(url):
    """
    Downloads and loads a public tabular dataset from a URL (CSV or Excel).
    Returns: pandas.DataFrame
    """
    if not url or not isinstance(url, str):
        raise DataLoaderError("❌ Could not load the dataset. Please check the file format or URL.")

    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise DataLoaderError("❌ Could not load the dataset. Please provide a valid HTTP or HTTPS URL.")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ChurnNexus/1.0"
        }
        response = requests.get(url, headers=headers, timeout=30, stream=True)
        if response.status_code != 200:
            raise DataLoaderError(f"❌ Could not load the dataset. Server returned status code {response.status_code}.")

        content = response.content
        if not content or len(content) == 0:
            raise DataLoaderError("❌ Could not load the dataset. The remote file is empty.")

        # Determine file type from URL or Content-Type
        lower_url = url.lower().split("?")[0]
        content_type = response.headers.get("Content-Type", "").lower()

        is_excel = (
            lower_url.endswith(".xlsx") or lower_url.endswith(".xls") or
            "spreadsheet" in content_type or "excel" in content_type
        )

        if is_excel:
            try:
                df = pd.read_excel(io.BytesIO(content))
                if not df.empty:
                    return df
            except Exception:
                pass

        # Try CSV
        try:
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8")
            if not df.empty:
                return df
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(content), encoding="latin1")
            if not df.empty:
                return df
        except Exception:
            # Fallback: if it wasn't recognized as CSV, try Excel as backup
            try:
                df = pd.read_excel(io.BytesIO(content))
                if not df.empty:
                    return df
            except Exception:
                pass

        raise DataLoaderError("❌ Could not load the dataset. The file content is not a supported CSV or Excel tabular format.")

    except DataLoaderError:
        raise
    except requests.exceptions.RequestException:
        raise DataLoaderError("❌ Could not load the dataset. Please check the file format or URL.")
    except Exception:
        raise DataLoaderError("❌ Could not load the dataset. Please check the file format or URL.")


def load_huggingface(dataset_id):
    """
    Loads a dataset from Hugging Face by dataset ID using the `datasets` library.
    Returns: pandas.DataFrame
    """
    if not dataset_id or not isinstance(dataset_id, str):
        raise DataLoaderError("❌ Dataset could not be found on Hugging Face. Check the dataset ID and try again.")

    dataset_id = dataset_id.strip()

    try:
        import datasets
    except ImportError:
        raise DataLoaderError("Hugging Face `datasets` library is not installed.")

    try:
        ds = datasets.load_dataset(dataset_id)
    except Exception as e:
        raise DataLoaderError("❌ Dataset could not be found on Hugging Face. Check the dataset ID and try again.")

    try:
        # Convert to pandas DataFrame
        if isinstance(ds, datasets.DatasetDict):
            if "train" in ds:
                df = ds["train"].to_pandas()
            else:
                first_split = list(ds.keys())[0]
                df = ds[first_split].to_pandas()
        elif isinstance(ds, datasets.Dataset):
            df = ds.to_pandas()
        else:
            raise DataLoaderError("❌ Could not convert Hugging Face dataset to a tabular format.")

        if df.empty:
            raise DataLoaderError("❌ The selected Hugging Face dataset split is empty.")

        return df

    except DataLoaderError:
        raise
    except Exception as e:
        raise DataLoaderError(f"❌ Could not process Hugging Face dataset into a DataFrame: {str(e)}")


def _build_db_engine(db_type, connection_params=None, sqlite_file=None):
    """
    Builds a SQLAlchemy engine for SQLite, MySQL, or PostgreSQL.
    """
    import sqlalchemy

    db_type = (db_type or "").strip().lower()

    if db_type == "sqlite":
        if not sqlite_file or not os.path.exists(sqlite_file):
            raise DataLoaderError("❌ SQLite database file not found. Please select or upload a valid .db or .sqlite file.")
        norm_path = os.path.abspath(sqlite_file).replace("\\", "/")
        return sqlalchemy.create_engine(f"sqlite:///{norm_path}")

    elif db_type in ("mysql", "mariadb"):
        params = connection_params or {}
        host = params.get("host", "localhost")
        port = params.get("port", 3306)
        database = params.get("database", "")
        username = urllib.parse.quote_plus(str(params.get("username", "")))
        password = urllib.parse.quote_plus(str(params.get("password", "")))

        if not database:
            raise DataLoaderError("❌ Database name is required to connect to MySQL.")

        uri = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
        return sqlalchemy.create_engine(uri, pool_pre_ping=True, connect_args={"connect_timeout": 10})

    elif db_type in ("postgresql", "postgres"):
        params = connection_params or {}
        host = params.get("host", "localhost")
        port = params.get("port", 5432)
        database = params.get("database", "")
        username = urllib.parse.quote_plus(str(params.get("username", "")))
        password = urllib.parse.quote_plus(str(params.get("password", "")))

        if not database:
            raise DataLoaderError("❌ Database name is required to connect to PostgreSQL.")

        uri = f"postgresql+pg8000://{username}:{password}@{host}:{port}/{database}"
        return sqlalchemy.create_engine(uri, pool_pre_ping=True, connect_args={"timeout": 10})

    else:
        raise DataLoaderError(f"❌ Unsupported database type '{db_type}'. Supported types: SQLite, MySQL, PostgreSQL.")


def get_sql_tables(db_type, connection_params=None, sqlite_file=None):
    """
    Connects to database and lists user tables.
    Returns: list of table names
    """
    db_type = (db_type or "").strip().lower()

    # Fast path for SQLite using standard library sqlite3
    if db_type == "sqlite":
        if not sqlite_file or not os.path.exists(sqlite_file):
            raise DataLoaderError("❌ Unable to connect to the database. Please verify the SQLite file.")
        try:
            conn = sqlite3.connect(sqlite_file)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            if not tables:
                raise DataLoaderError("❌ Connected successfully, but no tables were found in this database.")
            return sorted(tables)
        except DataLoaderError:
            raise
        except Exception:
            raise DataLoaderError("❌ Unable to connect to the database. Please verify the connection details.")

    # MySQL and PostgreSQL via SQLAlchemy
    try:
        import sqlalchemy
        engine = _build_db_engine(db_type, connection_params, sqlite_file)
        inspector = sqlalchemy.inspect(engine)
        tables = inspector.get_table_names()
        engine.dispose()

        if not tables:
            raise DataLoaderError("❌ Connected successfully, but no tables were found in this database.")
        return sorted(tables)

    except DataLoaderError:
        raise
    except Exception:
        raise DataLoaderError("❌ Unable to connect to the database. Please verify the connection details.")


def load_sql_table(db_type, connection_params=None, table_name=None, sqlite_file=None):
    """
    Queries an entire table from the specified database into a pandas DataFrame.
    Returns: pandas.DataFrame
    """
    if not table_name:
        raise DataLoaderError("❌ Please select a table to load.")

    # Basic sanitization of table name to prevent SQL injection
    if not re.match(r"^[A-Za-z0-9_\.\-]+$", table_name):
        raise DataLoaderError("❌ Invalid table name specified.")

    db_type = (db_type or "").strip().lower()

    # Fast path for SQLite
    if db_type == "sqlite":
        if not sqlite_file or not os.path.exists(sqlite_file):
            raise DataLoaderError("❌ Unable to connect to the database. SQLite file not found.")
        try:
            conn = sqlite3.connect(sqlite_file)
            query = f'SELECT * FROM "{table_name}"'
            df = pd.read_sql_query(query, conn)
            conn.close()
            if df.empty:
                raise DataLoaderError(f"❌ Table '{table_name}' contains no records.")
            return df
        except DataLoaderError:
            raise
        except Exception:
            raise DataLoaderError("❌ Unable to connect to the database. Please verify the connection details.")

    # MySQL & PostgreSQL
    try:
        import sqlalchemy
        engine = _build_db_engine(db_type, connection_params, sqlite_file)
        query = f'SELECT * FROM `{table_name}`' if "mysql" in db_type else f'SELECT * FROM "{table_name}"'
        with engine.connect() as conn:
            df = pd.read_sql_query(sqlalchemy.text(query), con=conn)
        engine.dispose()

        if df.empty:
            raise DataLoaderError(f"❌ Table '{table_name}' contains no records.")
        return df

    except DataLoaderError:
        raise
    except Exception:
        raise DataLoaderError("❌ Unable to connect to the database. Please verify the connection details.")
