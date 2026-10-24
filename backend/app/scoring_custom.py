"""Data-Driven Recommendation Engine for User-Uploaded Datasets in IntelliOps.
Supports arbitrary tabular formats (CSV, Excel .xlsx) with mandatory columns:
'Business Type' and 'Location Name'. Handles flexible optional columns, computes
association frequencies, normalizes numeric metrics, and provides explainable evidence.
"""

import csv
import io
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

from .xlsx_parser import parse_xlsx_bytes

# In-memory session store for uploaded datasets
DATASET_CACHE: Dict[str, Dict[str, Any]] = {}

MANDATORY_COLUMN_KEYS = ["business_type", "location_name"]


def _normalize_header(header: str) -> str:
    """Normalize column header: lowercase, stripped, spaces/underscores/hyphens unified."""
    cleaned = re.sub(r"[\s_\-]+", "_", header.strip().lower())
    return cleaned


def _find_column_mapping(headers: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """Identify mandatory and optional columns from header list.
    
    Returns:
        (mandatory_map, optional_headers)
        e.g. ({"business_type": "Business Type", "location_name": "Location Name"}, ["Footfall", "Rent"])
    """
    mandatory_map = {}
    optional_headers = []

    for h in headers:
        if not h or not str(h).strip():
            continue
        orig = str(h).strip()
        norm = _normalize_header(orig)

        # Check Business Type variants
        if norm in ("business_type", "businesstype", "business_category", "business", "category", "industry"):
            if "business_type" not in mandatory_map:
                mandatory_map["business_type"] = orig
                continue

        # Check Location Name variants
        if norm in ("location_name", "locationname", "location", "place_name", "candidate_location", "area_name", "location_title"):
            if "location_name" not in mandatory_map:
                mandatory_map["location_name"] = orig
                continue

        optional_headers.append(orig)

    return mandatory_map, optional_headers


def _infer_column_type(values: List[Any]) -> str:
    """Infer data type of a column based on non-null values."""
    non_nulls = [v for v in values if v is not None and str(v).strip() != ""]
    if not non_nulls:
        return "text"

    # Check boolean
    bool_strings = {"true", "false", "yes", "no", "1", "0", "t", "f"}
    if all(str(v).strip().lower() in bool_strings for v in non_nulls):
        return "boolean"

    # Check numeric
    numeric_count = 0
    for v in non_nulls:
        try:
            float(str(v).replace(",", ""))
            numeric_count += 1
        except ValueError:
            pass

    if numeric_count / len(non_nulls) >= 0.85:
        return "numeric"

    # Check categorical (low cardinality)
    unique_vals = set(str(v).strip().lower() for v in non_nulls)
    if len(unique_vals) <= max(5, int(len(non_nulls) * 0.25)):
        return "categorical"

    return "text"


def parse_and_validate_dataset(
    raw_bytes: bytes,
    filename: str
) -> Dict[str, Any]:
    """Parse raw CSV or XLSX bytes, validate mandatory columns, and build inspection summary."""
    filename_lower = filename.lower()
    rows_data: List[List[Any]] = []

    if filename_lower.endswith(".csv"):
        # Try UTF-8 with BOM, then Latin-1
        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw_bytes.decode("latin-1")
        reader = csv.reader(io.StringIO(text))
        for row in reader:
            if any(str(c).strip() for c in row):
                rows_data.append(row)
    elif filename_lower.endswith((".xlsx", ".xls")):
        try:
            rows_data = parse_xlsx_bytes(raw_bytes)
        except Exception as exc:
            raise ValueError(f"Could not parse Excel spreadsheet: {exc}") from exc
    else:
        raise ValueError("Unsupported file format. Please upload a CSV (.csv) or Excel (.xlsx) file.")

    if not rows_data or len(rows_data) < 2:
        raise ValueError("The uploaded file is empty or contains no data rows beyond headers.")

    raw_headers = [str(c).strip() for c in rows_data[0]]
    if not any(raw_headers):
        raise ValueError("The uploaded file does not have a valid header row.")

    mandatory_map, optional_headers = _find_column_mapping(raw_headers)

    missing_mandatory = []
    if "business_type" not in mandatory_map:
        missing_mandatory.append("'Business Type'")
    if "location_name" not in mandatory_map:
        missing_mandatory.append("'Location Name'")

    if missing_mandatory:
        present_cols = [f"'{h}'" for h in raw_headers if h]
        raise ValueError(
            f"Missing required mandatory column(s): {', '.join(missing_mandatory)}. "
            f"Detected columns in file: [{', '.join(present_cols)}]. "
            "Please ensure your dataset contains both 'Business Type' and 'Location Name' columns."
        )

    bt_orig_header = mandatory_map["business_type"]
    loc_orig_header = mandatory_map["location_name"]

    bt_idx = raw_headers.index(bt_orig_header)
    loc_idx = raw_headers.index(loc_orig_header)

    accepted_rows: List[Dict[str, Any]] = []
    rejected_rows_count = 0
    rejected_reasons: List[str] = []

    # Map header indices
    header_indices = {h: idx for idx, h in enumerate(raw_headers) if h}

    for row_idx, row in enumerate(rows_data[1:], start=2):
        # Discard completely empty row
        if not any(str(c).strip() for c in row):
            continue

        bt_val = str(row[bt_idx]).strip() if bt_idx < len(row) and row[bt_idx] is not None else ""
        loc_val = str(row[loc_idx]).strip() if loc_idx < len(row) and row[loc_idx] is not None else ""

        if not bt_val or not loc_val:
            rejected_rows_count += 1
            if len(rejected_reasons) < 5:
                rejected_reasons.append(f"Row {row_idx}: Missing required '{bt_orig_header}' or '{loc_orig_header}'.")
            continue

        # Extract all columns
        row_dict: Dict[str, Any] = {
            "business_type": bt_val,
            "location_name": loc_val,
            "_row_index": row_idx,
        }

        for h, idx in header_indices.items():
            val = row[idx] if idx < len(row) else ""
            cleaned_val = str(val).strip() if val is not None else ""
            row_dict[h] = cleaned_val

        accepted_rows.append(row_dict)

    if not accepted_rows:
        raise ValueError(
            f"No valid records found in dataset. All {rejected_rows_count} data rows were rejected "
            "because either 'Business Type' or 'Location Name' was empty."
        )

    # Column type inference & metadata
    column_infos = []
    for h in raw_headers:
        if not h:
            continue
        vals = [r.get(h) for r in accepted_rows]
        inferred = _infer_column_type(vals)
        non_nulls = [v for v in vals if v is not None and str(v).strip() != ""]
        unique_vals = list(dict.fromkeys(str(v).strip() for v in non_nulls if str(v).strip()))
        column_infos.append({
            "name": h,
            "original_name": h,
            "inferred_type": inferred,
            "non_null_count": len(non_nulls),
            "unique_count": len(unique_vals),
            "sample_values": unique_vals[:3]
        })

    # Available business types
    b_types_dict: Dict[str, int] = {}
    for r in accepted_rows:
        bt = r["business_type"]
        b_types_dict[bt] = b_types_dict.get(bt, 0) + 1

    available_business_types = sorted(b_types_dict.keys(), key=lambda k: (-b_types_dict[k], k))
    unique_locations = sorted(list(set(r["location_name"] for r in accepted_rows)))

    dataset_id = f"ds-{uuid.uuid4().hex[:10]}"
    warnings: List[str] = []

    if len(accepted_rows) < 5:
        warnings.append("Small dataset (fewer than 5 records): recommendation rankings should be treated as preliminary.")
    if rejected_rows_count > 0:
        warnings.append(f"{rejected_rows_count} row(s) were excluded because of missing Business Type or Location Name.")
    if not optional_headers:
        warnings.append("Dataset contains only the two mandatory columns. Rankings are computed purely from association frequencies and co-occurrence.")

    summary = {
        "dataset_id": dataset_id,
        "filename": filename,
        "total_rows": len(rows_data) - 1,
        "accepted_rows": len(accepted_rows),
        "rejected_rows": rejected_rows_count,
        "rejected_reasons": rejected_reasons,
        "columns": column_infos,
        "mandatory_columns_found": {
            "business_type": bt_orig_header,
            "location_name": loc_orig_header
        },
        "optional_columns_found": optional_headers,
        "available_business_types": available_business_types,
        "unique_locations_count": len(unique_locations),
        "warnings": warnings,
    }

    # Store in memory cache
    DATASET_CACHE[dataset_id] = {
        "summary": summary,
        "rows": accepted_rows,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    return {
        "summary": summary,
        "rows": accepted_rows,
        "preview": accepted_rows[:10]
    }


def recommend_custom_locations(
    dataset_id: Optional[str] = None,
    rows: Optional[List[Dict[str, Any]]] = None,
    selected_business_type: str = "",
    min_occurrences: int = 1,
    weight_frequency: float = 0.6,
    weight_metrics: float = 0.4,
    budget_filter: Optional[float] = None,
    metric_overrides: Optional[Dict[str, Dict[str, float]]] = None
) -> Dict[str, Any]:
    """Generate recommendations from user dataset for a selected business type.
    
    Combines association frequency and any detected optional numeric columns.
    """
    if not rows:
        if not dataset_id or dataset_id not in DATASET_CACHE:
            raise ValueError("Dataset not found. Please upload a dataset file first.")
        cached = DATASET_CACHE[dataset_id]
        rows = cached["rows"]
        summary = cached["summary"]
    else:
        # Re-derive summary if rows passed directly
        summary = {
            "dataset_id": dataset_id or "direct-payload",
            "filename": "Uploaded Dataset",
            "total_rows": len(rows),
            "accepted_rows": len(rows),
            "rejected_rows": 0,
            "rejected_reasons": [],
            "columns": [],
            "mandatory_columns_found": {"business_type": "Business Type", "location_name": "Location Name"},
            "optional_columns_found": [k for k in rows[0].keys() if k not in ("business_type", "location_name", "_row_index")] if rows else [],
            "available_business_types": sorted(list(set(r.get("business_type", "") for r in rows if r.get("business_type")))),
            "unique_locations_count": len(set(r.get("location_name", "") for r in rows if r.get("location_name"))),
            "warnings": []
        }

    if not rows:
        raise ValueError("No data rows available to analyze.")

    # Match business type (case-insensitive)
    target_bt_lower = selected_business_type.strip().lower()
    matching_rows = [
        r for r in rows
        if r.get("business_type", "").strip().lower() == target_bt_lower
    ]

    if not matching_rows:
        # Provide helpful error listing available types
        available = summary.get("available_business_types", [])
        raise ValueError(
            f"No records found for business type '{selected_business_type}' in the uploaded dataset. "
            f"Available business types: {', '.join(available[:10])}."
        )

    # Co-location map across ALL rows
    all_locations_bt_map: Dict[str, set] = {}
    total_loc_counts: Dict[str, int] = {}
    for r in rows:
        loc = r.get("location_name", "").strip()
        bt = r.get("business_type", "").strip()
        if loc:
            if loc not in all_locations_bt_map:
                all_locations_bt_map[loc] = set()
            if bt:
                all_locations_bt_map[loc].add(bt)
            total_loc_counts[loc] = total_loc_counts.get(loc, 0) + 1

    # Group matching rows by location
    loc_groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in matching_rows:
        loc = r.get("location_name", "").strip()
        if not loc:
            continue
        if loc not in loc_groups:
            loc_groups[loc] = []
        loc_groups[loc].append(r)

    # Filter by min_occurrences
    eligible_locs = {loc: grp for loc, grp in loc_groups.items() if len(grp) >= min_occurrences}
    if not eligible_locs:
        eligible_locs = loc_groups  # Fallback so user gets results

    max_freq = max(len(grp) for grp in eligible_locs.values()) if eligible_locs else 1
    total_bt_records = len(matching_rows)

    # Identify optional numeric columns from the dataset
    sample_row = rows[0]
    optional_keys = [k for k in sample_row.keys() if k not in ("business_type", "location_name", "_row_index")]
    
    numeric_columns: List[str] = []
    cost_columns: List[str] = []

    for k in optional_keys:
        vals = [r.get(k) for r in rows if r.get(k) is not None and str(r.get(k)).strip() != ""]
        if vals:
            num_success = 0
            for v in vals:
                try:
                    float(str(v).replace(",", ""))
                    num_success += 1
                except ValueError:
                    pass
            if num_success / len(vals) >= 0.75:
                numeric_columns.append(k)
                k_lower = k.lower()
                if any(term in k_lower for term in ["rent", "cost", "price", "expense"]):
                    cost_columns.append(k)

    # Find min/max for each numeric column to support 0-100 normalization
    num_col_stats: Dict[str, Tuple[float, float, bool]] = {}  # col -> (min_val, max_val, is_inverse)
    for col in numeric_columns:
        vals = []
        for r in rows:
            v_str = str(r.get(col, "")).replace(",", "").strip()
            try:
                vals.append(float(v_str))
            except ValueError:
                pass
        if vals:
            min_v, max_v = min(vals), max(vals)
            col_lower = col.lower()
            is_inv = any(term in col_lower for term in ["rent", "cost", "price", "expense", "competition", "distance", "risk"])
            num_col_stats[col] = (min_v, max_v, is_inv)

    recommendations: List[Dict[str, Any]] = []

    for loc, records in eligible_locs.items():
        occ = len(records)
        assoc_pct = round((occ / total_bt_records) * 100, 1)

        # Baseline frequency utility (0-100)
        # Log-dampened frequency so extreme outliers do not crush standard frequencies
        freq_ratio = math.log1p(occ) / math.log1p(max_freq) if max_freq > 1 else 1.0
        frequency_score = round(40.0 + 60.0 * freq_ratio, 1)

        # Co-located business types
        co_located = sorted(list(all_locations_bt_map.get(loc, set()) - {selected_business_type}))

        # Aggregate numeric metrics for this location
        numeric_metrics: Dict[str, float] = {}
        metric_utility_scores: List[float] = []

        for col, (min_v, max_v, is_inv) in num_col_stats.items():
            col_vals = []
            for r in records:
                v_str = str(r.get(col, "")).replace(",", "").strip()
                try:
                    col_vals.append(float(v_str))
                except ValueError:
                    pass
            if col_vals:
                avg_val = sum(col_vals) / len(col_vals)
                # Check for what-if scenario override
                if metric_overrides and loc in metric_overrides and col in metric_overrides[loc]:
                    avg_val = metric_overrides[loc][col]

                numeric_metrics[col] = round(avg_val, 2)
                
                # Normalize to 0-100
                if max_v > min_v:
                    norm = (avg_val - min_v) / (max_v - min_v) * 100.0
                    norm = max(0.0, min(100.0, norm))
                else:
                    norm = 50.0

                u = (100.0 - norm) if is_inv else norm
                metric_utility_scores.append(u)

        # Calculate final composite score
        if metric_utility_scores:
            avg_metric_score = sum(metric_utility_scores) / len(metric_utility_scores)
            composite_score = round(weight_frequency * frequency_score + weight_metrics * avg_metric_score, 1)
        else:
            composite_score = frequency_score

        # Check budget filter if applicable
        budget_exceeded = False
        if budget_filter and budget_filter > 0 and cost_columns:
            for c_col in cost_columns:
                if c_col in numeric_metrics and numeric_metrics[c_col] > budget_filter:
                    budget_exceeded = True
                    composite_score = max(10.0, composite_score - 25.0)

        # Text/categorical values for evidence
        text_metrics: Dict[str, str] = {}
        for col in optional_keys:
            if col not in numeric_columns:
                unique_c_vals = list(dict.fromkeys(str(r.get(col, "")).strip() for r in records if str(r.get(col, "")).strip()))
                if unique_c_vals:
                    text_metrics[col] = ", ".join(unique_c_vals[:3])

        # Rationales
        strengths: List[str] = []
        weaknesses: List[str] = []
        warnings: List[str] = []

        if occ == max_freq and occ > 1:
            strengths.append(f"Highest association frequency in your dataset ({occ} records for {selected_business_type}).")
        elif occ > 1:
            strengths.append(f"Strong occurrence frequency ({occ} records, {assoc_pct}% of {selected_business_type} data).")
        else:
            strengths.append(f"Directly recorded in dataset for {selected_business_type}.")

        if co_located:
            strengths.append(f"Co-located with complementary businesses: {', '.join(co_located[:3])}.")

        # Numeric strengths & weaknesses
        for col, u in zip(numeric_metrics.keys(), metric_utility_scores):
            if u >= 75:
                strengths.append(f"Favorable {col} ({numeric_metrics[col]}).")
            elif u < 45:
                weaknesses.append(f"Suboptimal {col} ({numeric_metrics[col]}).")

        if occ == 1:
            warnings.append("Single occurrence in dataset: treat ranking as preliminary.")
        if budget_exceeded:
            warnings.append(f"Recorded cost exceeds your scenario budget limit of ₹{budget_filter:,}.")
        if not numeric_metrics:
            weaknesses.append("No numeric metrics supplied in dataset; ranking relies on frequency and co-occurrence.")

        if not strengths:
            strengths.append("Matches selected business type criteria in the uploaded dataset.")
        if not weaknesses:
            weaknesses.append("No negative performance metrics indicated in dataset.")

        next_steps = [
            f"Cross-reference this dataset record for '{loc}' against active commercial listings.",
            "Verify footfall, zoning, and actual leasing availability on-site.",
            "Collect revenue and rent figures to enrich subsequent iterations of this model."
        ]

        evidence_records = [
            {
                "row_index": r.get("_row_index", 0),
                "location_name": loc,
                "business_type": selected_business_type,
                "additional_data": {k: r.get(k) for k in optional_keys if r.get(k) is not None}
            }
            for r in records
        ]

        classification = "High Association" if composite_score >= 75 else "Moderate Association" if composite_score >= 50 else "Preliminary Match"

        recommendations.append({
            "id": f"custom-{uuid.uuid4().hex[:8]}",
            "location_name": loc,
            "business_type": selected_business_type,
            "score": composite_score,
            "classification": classification,
            "occurrence_count": occ,
            "total_business_records": total_bt_records,
            "association_percentage": assoc_pct,
            "co_located_business_types": co_located,
            "numeric_metrics": numeric_metrics,
            "text_metrics": text_metrics,
            "strengths": strengths[:3],
            "weaknesses": weaknesses[:3],
            "warnings": warnings,
            "next_steps": next_steps,
            "evidence_records": evidence_records
        })

    # Sort deterministically
    recommendations.sort(key=lambda x: (-x["score"], -x["occurrence_count"], x["location_name"].lower()))
    for rank, item in enumerate(recommendations, start=1):
        item["rank"] = rank

    return {
        "recommendations": recommendations,
        "selected_business_type": selected_business_type,
        "total_locations_recommended": len(recommendations),
        "dataset_summary": summary,
        "metadata": {
            "method": "Data-Driven Association and Utility Engine",
            "method_version": "2.0.0",
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "locations_evaluated": len(recommendations),
            "disclaimer": "Recommendations are derived strictly from associations and values in your uploaded dataset. They do not predict future business success. Validate real-world market evidence before making financial commitments."
        }
    }
