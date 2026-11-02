"""Pure Python OpenXML Spreadsheet (.xlsx) parser.
Uses standard library zipfile and xml.etree.ElementTree with zero external dependencies.
"""

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Tuple, Any

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def _col_to_index(col_letters: str) -> int:
    """Convert column letters like 'A', 'B', 'Z', 'AA' to 0-based index."""
    idx = 0
    for char in col_letters.upper():
        if "A" <= char <= "Z":
            idx = idx * 26 + (ord(char) - ord("A") + 1)
    return max(0, idx - 1)


def _split_cell_ref(cell_ref: str) -> Tuple[int, int]:
    """Parse cell reference like 'B3' into (row_0_based, col_0_based)."""
    match = re.match(r"^([A-Za-z]+)(\d+)$", cell_ref)
    if not match:
        return 0, 0
    col_str, row_str = match.groups()
    return int(row_str) - 1, _col_to_index(col_str)


def parse_xlsx_bytes(file_bytes: bytes) -> List[List[Any]]:
    """Parse an .xlsx file from bytes into a list of row lists.
    
    Extracts shared strings and primary worksheet cells.
    Handles cell gaps gracefully using cell coordinates.
    """
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
        # 1. Parse shared strings if present
        shared_strings: List[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in tree.findall(".//main:si", NS) or tree.findall(".//si"):
                # Concatenate all <t> texts within this string item
                parts = []
                for t in si.findall(".//main:t", NS) or si.findall(".//t"):
                    parts.append(t.text or "")
                shared_strings.append("".join(parts))

        # 2. Find primary worksheet
        sheet_path = "xl/worksheets/sheet1.xml"
        if sheet_path not in z.namelist():
            for name in sorted(z.namelist()):
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
                    sheet_path = name
                    break

        if sheet_path not in z.namelist():
            raise ValueError("No worksheet found in XLSX archive.")

        sheet_tree = ET.fromstring(z.read(sheet_path))
        rows_elements = sheet_tree.findall(".//main:row", NS) or sheet_tree.findall(".//row")

        parsed_rows: List[List[Any]] = []
        max_cols = 0

        for row_el in rows_elements:
            row_idx = int(row_el.get("r", "1")) - 1
            cells = row_el.findall(".//main:c", NS) or row_el.findall(".//c")
            
            row_dict = {}
            for c in cells:
                ref = c.get("r", "")
                if ref:
                    _, c_idx = _split_cell_ref(ref)
                else:
                    c_idx = len(row_dict)

                cell_type = c.get("t", "n")
                v_el = c.find(".//main:v", NS) if c.find(".//main:v", NS) is not None else c.find(".//v")
                val_text = v_el.text if v_el is not None else ""

                if cell_type == "s":
                    # Shared string
                    if val_text.isdigit() and int(val_text) < len(shared_strings):
                        val: Any = shared_strings[int(val_text)]
                    else:
                        val = val_text
                elif cell_type == "inlineStr":
                    # Inline string
                    t_nodes = c.findall(".//main:t", NS) or c.findall(".//t")
                    val = "".join(t.text or "" for t in t_nodes)
                elif cell_type == "b":
                    val = val_text in ("1", "true", "TRUE")
                else:
                    # Number or formula result
                    if val_text == "":
                        val = ""
                    else:
                        try:
                            val = float(val_text) if "." in val_text else int(val_text)
                        except ValueError:
                            val = val_text

                row_dict[c_idx] = val
                if c_idx + 1 > max_cols:
                    max_cols = c_idx + 1

            if row_dict:
                # Convert dict to row list with None padding for gaps
                row_list = [row_dict.get(i, "") for i in range(max(row_dict.keys()) + 1)]
                if any(str(x).strip() for x in row_list):
                    parsed_rows.append(row_list)

        # Normalize row lengths to rectangular grid
        rectangular_rows = []
        for r in parsed_rows:
            padded = r + [""] * (max_cols - len(r))
            rectangular_rows.append(padded)

        return rectangular_rows
