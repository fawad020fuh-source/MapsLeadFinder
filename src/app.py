from __future__ import annotations

import argparse
import logging
import os
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional

from dotenv import load_dotenv

from .api_client import GooglePlacesClient, PlaceResult
from .crawler import WebsiteCrawler
from .email_extractor import EmailExtractor
from .exporter import export_records

logger = logging.getLogger(__name__)
load_dotenv()


class ResultCache:
    """Simple SQLite-based cache to allow resuming interrupted runs."""

    def __init__(self, db_path: str = "output/cache.sqlite3"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT,
                    location TEXT,
                    place_id TEXT UNIQUE,
                    business_name TEXT,
                    payload TEXT
                )
                """
            )

    def upsert(self, keyword: str, location: str, record: PlaceResult) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO searches (keyword, location, place_id, business_name, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (keyword, location, record.place_id, record.name, str(record.to_row())),
            )

    def load(self, keyword: str, location: str) -> List[dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT payload FROM searches WHERE keyword = ? AND location = ? ORDER BY id",
                (keyword, location),
            ).fetchall()
        return [eval(row[0]) for row in rows]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MapsLeadFinder searches Google Maps and extracts business emails from public websites.")
    parser.add_argument("--keyword", default="dentist", help="Main keyword to search for")
    parser.add_argument("--location", default="Lahore, Pakistan", help="Location to search in")
    parser.add_argument("--max-results", type=int, default=30, help="Target maximum results")
    parser.add_argument("--radius-km", type=float, default=15.0, help="Search radius in kilometers")
    parser.add_argument("--deep-search", action="store_true", help="Split the area into a grid for broad discovery")
    parser.add_argument("--variation", action="append", dest="variations", default=[], help="Extra keyword variations")
    parser.add_argument("--output-dir", default="output", help="Directory for CSV/XLSX exports")
    parser.add_argument("--resume-db", default="output/cache.sqlite3", help="SQLite database used for resume support")
    return parser


def run_search(
    keyword: str,
    location: str,
    max_results: int,
    radius_km: float,
    deep_search: bool,
    variations: Optional[List[str]] = None,
    resume_db: str = "output/cache.sqlite3",
) -> List[dict]:
    """Run a full search, collect businesses, and extract public emails from each website."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is missing. Copy .env.example to .env and set your API key.")

    client = GooglePlacesClient(api_key=api_key)
    crawler = WebsiteCrawler()
    email_extractor = EmailExtractor(crawler)
    cache = ResultCache(resume_db)

    places = client.search_places(
        keyword=keyword,
        location=location,
        max_results=max_results,
        radius_km=radius_km,
        keyword_variations=variations,
        deep_search=deep_search,
    )

    records: List[dict] = []
    for place in places:
        emails: List[str] = []
        if place.website:
            try:
                emails = email_extractor.extract_from_website(place.website)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to extract emails from %s: %s", place.website, exc)
                emails = []

        row = place.to_row()
        row["Email(s)"] = "; ".join(emails)
        records.append(row)
        cache.upsert(keyword, location, place)

    return records


def run_cli() -> None:
    parser = build_parser()
    args = parser.parse_args()

    records = run_search(
        keyword=args.keyword,
        location=args.location,
        max_results=args.max_results,
        radius_km=args.radius_km,
        deep_search=args.deep_search,
        variations=args.variations,
        resume_db=args.resume_db,
    )
    csv_path, xlsx_path = export_records(records, output_dir=args.output_dir)
    print(f"Search complete. Results exported to: {csv_path} and {xlsx_path}")


def run_streamlit() -> None:
    """Minimal Streamlit app. This is intentionally compact but functional."""
    try:
        import streamlit as st
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("streamlit is required for the GUI mode: pip install -r requirements.txt") from exc

    st.title("MapsLeadFinder")
    st.caption("Find businesses from Google Maps and collect publicly listed contact emails from their website.")
    st.warning(
        "Users are responsible for following Google API terms, local email laws (CAN-SPAM, GDPR, etc.), and include an unsubscribe option and honest sender info when emailing."
    )

    with st.form("search_form"):
        keyword = st.text_input("Search keyword", "dentist")
        location = st.text_input("Location", "Lahore, Pakistan")
        max_results = st.number_input("Max results", min_value=1, max_value=250, value=30)
        radius_km = st.number_input("Radius (km)", min_value=1.0, max_value=200.0, value=15.0, step=1.0)
        deep_search = st.checkbox("Deep search (grid-based expansion)")
        variations = st.text_input("Keyword variations (comma separated)", "")
        submitted = st.form_submit_button("Search")

    if submitted:
        var_list = [v.strip() for v in variations.split(",") if v.strip()]
        with st.spinner("Searching Google Maps and processing websites..."):
            records = run_search(
                keyword=keyword,
                location=location,
                max_results=int(max_results),
                radius_km=float(radius_km),
                deep_search=deep_search,
                variations=var_list,
            )
        st.success(f"Found {len(records)} businesses.")
        st.dataframe(records)
        csv_path, xlsx_path = export_records(records, output_dir="output")
        st.download_button("Download CSV", data=csv_path.read_bytes(), file_name=csv_path.name, mime="text/csv")
        st.download_button("Download XLSX", data=xlsx_path.read_bytes(), file_name=xlsx_path.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    run_cli()

