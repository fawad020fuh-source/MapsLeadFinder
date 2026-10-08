from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians
from typing import List


@dataclass(frozen=True)
class Zone:
    name: str
    latitude: float
    longitude: float
    radius_km: float


def generate_grid_zones(center_lat: float, center_lon: float, radius_km: float = 15.0, cells_per_side: int = 3) -> List[Zone]:
    """Generate a square grid of smaller search zones around a central point.

    This is a lightweight approximation for deep-search behavior. Each zone is represented
    by a center point plus a search radius. Google Places API accepts a circle bias, so we
    use that for each zone instead of large broad-area queries.
    """
    if cells_per_side < 1:
        raise ValueError("cells_per_side must be at least 1")

    cell_count = max(1, cells_per_side)
    half_span_km = max(radius_km, 1.0)
    lat_delta_km = 2 * half_span_km / cell_count
    lon_delta_km = 2 * half_span_km / cell_count

    lat_step = lat_delta_km / 111.0
    lon_step = lon_delta_km / (111.0 * max(cos(radians(center_lat)), 0.1))

    zones: List[Zone] = []
    for row in range(cell_count):
        for col in range(cell_count):
            zone_lat = center_lat + (row - (cell_count - 1) / 2) * lat_step
            zone_lon = center_lon + (col - (cell_count - 1) / 2) * lon_step
            zones.append(
                Zone(
                    name=f"zone_{row}_{col}",
                    latitude=zone_lat,
                    longitude=zone_lon,
                    radius_km=max(radius_km / 2, 2.0),
                )
            )

    return zones


def paginate_in_zones(center_lat: float, center_lon: float, radius_km: float = 15.0, cells_per_side: int = 3):
    """Compatibility helper returning zone list."""
    return generate_grid_zones(center_lat, center_lon, radius_km, cells_per_side)

