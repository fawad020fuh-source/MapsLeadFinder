from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

from .grid import Zone, generate_grid_zones

logger = logging.getLogger(__name__)
load_dotenv()


@dataclass
class PlaceResult:
    name: str
    address: str
    phone: str = ""
    website: str = ""
    rating: Optional[float] = None
    review_count: int = 0
    maps_url: str = ""
    place_id: str = ""
    category: str = ""
    search_keyword: str = ""
    location: str = ""
    date_collected: str = ""

    def to_row(self) -> Dict[str, Any]:
        return {
            "Business Name": self.name,
            "Category": self.category,
            "Address": self.address,
            "Phone": self.phone,
            "Website": self.website,
            "Email(s)": "",
            "Rating": self.rating,
            "Reviews": self.review_count,
            "Maps URL": self.maps_url,
            "Search Keyword": self.search_keyword,
            "Location": self.location,
            "Date Collected": self.date_collected,
            "Place ID": self.place_id,
        }


class GooglePlacesClient:
    """Thin wrapper around the Google Places API (New) Text Search endpoint."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 20.0):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.timeout = timeout
        if not self.api_key:
            raise ValueError("Missing Google API key. Set GOOGLE_API_KEY in your environment or .env file.")

    def geocode_location(self, location: str) -> Tuple[float, float, str]:
        """Geocode a plain-text location string."""
        params = {"address": location, "key": self.api_key}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get("https://maps.googleapis.com/maps/api/geocode/json", params=params)
            resp.raise_for_status()
            payload = resp.json()
        if payload.get("status") not in {"OK", "ZERO_RESULTS"}:
            raise RuntimeError(f"Geocoding failed: {payload.get('error_message') or payload.get('status')}")
        if not payload.get("results"):
            raise ValueError(f"No geocoded result found for location: {location}")
        result = payload["results"][0]
        lat = result["geometry"]["location"]["lat"]
        lng = result["geometry"]["location"]["lng"]
        return float(lat), float(lng), result.get("formatted_address", location)

    def _search_text(self, keyword: str, latitude: float, longitude: float, radius_m: int, page_token: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "textQuery": keyword,
            "locationBias": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius_m,
                }
            },
            "pageSize": 20,
            "languageCode": "en",
        }
        if page_token:
            payload["pageToken"] = page_token

        headers = {"Content-Type": "application/json; charset=utf-8"}
        url = "https://places.googleapis.com/v1/places:searchText"
        params = {"key": self.api_key}
        with httpx.Client(timeout=self.timeout, headers=headers) as client:
            resp = client.post(url, params=params, content=json.dumps(payload))
            data = resp.json()
            if resp.status_code >= 400:
                error = data.get("error", {})
                message = error.get("message", resp.text)
                if "API key" in message or "key" in message.lower():
                    raise PermissionError("Invalid Google API key or missing Places API access.")
                if "quota" in message.lower() or "daily limit" in message.lower():
                    raise RuntimeError("Google Places API quota exceeded.")
                raise RuntimeError(f"Places API request failed: {message}")
            return data

    def fetch_place_details(self, place_id: str) -> Dict[str, Any]:
        fields = [
            "id",
            "displayName",
            "formattedAddress",
            "types",
            "websiteUri",
            "internationalPhoneNumber",
            "nationalPhoneNumber",
            "rating",
            "userRatingCount",
            "googleMapsUri",
            "photos",
        ]
        url = f"https://places.googleapis.com/v1/places/{place_id}"
        params = {"key": self.api_key, "fields": ",".join(fields)}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params)
            data = resp.json()
            if resp.status_code >= 400:
                error = data.get("error", {})
                message = error.get("message", resp.text)
                if "not found" in message.lower():
                    logger.warning("Place details not found for %s: %s", place_id, message)
                    return {}
                raise RuntimeError(f"Failed to fetch details for {place_id}: {message}")
            return data

    def search_places(
        self,
        keyword: str,
        location: str,
        max_results: int,
        radius_km: Optional[float] = None,
        keyword_variations: Optional[List[str]] = None,
        deep_search: bool = False,
        grid_cells: int = 3,
    ) -> List[PlaceResult]:
        """Return a deduplicated list of businesses matching keyword + location."""
        queries = [keyword]
        if keyword_variations:
            for variation in keyword_variations:
                candidate = variation.strip()
                if candidate and candidate.lower() not in {q.lower() for q in queries}:
                    queries.append(candidate)

        center_lat, center_lon, formatted_location = self.geocode_location(location)
        radius_m = int((radius_km or 10.0) * 1000)
        all_results: Dict[str, PlaceResult] = {}
        seen_queries: set[str] = set()

        for query in queries:
            if query in seen_queries:
                continue
            seen_queries.add(query)
            if deep_search:
                zones = generate_grid_zones(center_lat, center_lon, radius_km=max(radius_km or 10.0, 1.0), cells_per_side=max(2, grid_cells))
                for zone in zones:
                    try:
                        zone_results = self._collect_place_results(query, zone, location, max_results, all_results)
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.warning("Failed to process zone %s: %s", zone.name, exc)
                        continue
                    if len(all_results) >= max_results:
                        break
            else:
                try:
                    self._collect_place_results(query, Zone("center", center_lat, center_lon, radius_m / 1000), location, max_results, all_results)
                except Exception as exc:
                    logger.warning("Search failed for query %q: %s", query, exc)
                    continue
            if len(all_results) >= max_results:
                break

        ordered = list(all_results.values())
        ordered.sort(key=lambda item: (item.name.lower(), item.address.lower()))
        return ordered[:max_results]

    def _collect_place_results(
        self,
        keyword: str,
        zone: Zone,
        location: str,
        max_results: int,
        accumulator: Dict[str, PlaceResult],
    ) -> None:
        next_page_token: Optional[str] = None
        while True:
            data = self._search_text(keyword, zone.latitude, zone.longitude, int(zone.radius_km * 1000), next_page_token)
            for item in data.get("places", []):
                if len(accumulator) >= max_results:
                    return
                place_id = item.get("id") or item.get("place_id")
                if not place_id:
                    continue
                if place_id in accumulator:
                    continue
                details = self.fetch_place_details(place_id)
                place = self._map_place_result(item, details, keyword, location)
                if place and place.name:
                    accumulator[place_id] = place
            next_token = data.get("nextPageToken")
            if not next_token:
                break
            next_page_token = next_token
            time.sleep(2.0)

    def _map_place_result(
        self,
        item: Dict[str, Any],
        details: Dict[str, Any],
        keyword: str,
        location: str,
    ) -> Optional[PlaceResult]:
        details = details or {}
        display = item.get("displayName") or details.get("displayName") or {}
        name = (display.get("text") if isinstance(display, dict) else str(display)) or "Unknown business"
        formatted_address = item.get("formattedAddress") or details.get("formattedAddress") or ""
        website = item.get("websiteUri") or details.get("websiteUri") or ""
        phone = item.get("internationalPhoneNumber") or details.get("internationalPhoneNumber") or details.get("nationalPhoneNumber") or ""
        rating = item.get("rating") or details.get("rating")
        reviews = item.get("userRatingCount") or details.get("userRatingCount") or 0
        maps_url = item.get("googleMapsUri") or details.get("googleMapsUri") or ""
        types = item.get("types") or details.get("types") or []
        category = types[0].replace("_", " ").title() if types else "Business"
        place_id = item.get("id") or details.get("id") or ""
        if not place_id:
            return None
        record = PlaceResult(
            name=name,
            address=formatted_address,
            phone=phone,
            website=website,
            rating=float(rating) if rating is not None else None,
            review_count=int(reviews),
            maps_url=maps_url,
            place_id=place_id,
            category=category,
            search_keyword=keyword,
            location=location,
            date_collected=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )
        return record


__all__ = ["GooglePlacesClient", "PlaceResult"]
