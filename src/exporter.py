from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List

import pandas as pd

logger = logging.getLogger(__name__)


def export_records(records: Iterable[dict], output_dir: str = "output") -> tuple[Path, Path]:
    """Export a list of dict-like records to CSV and XLSX."""
    records = list(records)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    csv_path = output_path / "businesses.csv"
    xlsx_path = output_path / "businesses.xlsx"

    df = pd.DataFrame.from_records(records)
    columns = [
        "Business Name",
        "Category",
        "Address",
        "Phone",
        "Website",
        "Email(s)",
        "Rating",
        "Reviews",
        "Maps URL",
        "Search Keyword",
        "Location",
        "Date Collected",
    ]
    df = df.reindex(columns=columns, fill_value="")
    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    logger.info("Exported %d rows to %s and %s", len(df), csv_path, xlsx_path)
    return csv_path, xlsx_path


__all__ = ["export_records"]
