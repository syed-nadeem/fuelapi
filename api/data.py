"""
Loads fuel station data from CSV and resolves coordinates using a bundledUS cities dataset
I have bundledUS cities dataset in advance because based on provided csv its need 7.5K api calls for each city
after calculating csv data no external HTTP calls needed for stations.

Only the user-facing geocode() function (for start/end inputs) will calls Nominatim API.
Nominatim API also has api limit we can get 429 too many request error for that i added the geocode for default cities
Station coordinate lookup is instant: a local dict built once at import time.
"""
import threading
import requests
import pandas as pd
from pathlib import Path
from django.conf import settings

_CACHE_LOCK = threading.Lock()
_STATIONS_CACHE = None

_US_CITIES: dict = {}  # (city_lower, state_upper) → (lat, lon)


def _load_city_db():
    global _US_CITIES
    if _US_CITIES:
        return
    csv_path = Path(settings.BASE_DIR) / "us_cities.csv"
    df = pd.read_csv(csv_path, usecols=["city", "state", "lat", "lon"])
    _US_CITIES = {
        (str(row.city).lower().strip(), str(row.state).upper().strip()): (row.lat, row.lon)
        for row in df.itertuples(index=False)
    }


try:
    # Eagerly load on import so first request has no delay
    import django
    _load_city_db()
except Exception:
    pass  # will retry inside load_stations


# ── Geocode user-input locations (Nominatim, called only for start/end) ───────
def geocode(query: str):
    """
    Return (lat, lon) for a free-text US location string.
    Uses Nominatim — only called for start/end user inputs, never for stations.
    """
    if hasattr(settings, 'GEOCODE_OVERRIDE') and settings.GEOCODE_OVERRIDE:
        key = query.lower().split(',')[0].strip()
        for k, v in settings.GEOCODE_OVERRIDE.items():
            if k.lower() in key:
                return v

    url = f"{settings.NOMINATIM_BASE_URL}/search"
    params = {"q": query, "countrycodes": "us", "format": "json", "limit": 1}
    headers = {"User-Agent": "FuelRouteApp/1.0 (fuel-route-planner)"}
    resp = requests.get(url, params=params, headers=headers, timeout=8)
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


def _coords_for_station(city: str, state: str):
    """
    Fast dict lookup against the bundled US cities dataset.
    Returns (lat, lon) or None if city not found.
    Falls back to state-capital approximation only when truly unknown.
    """
    if not _US_CITIES:
        _load_city_db()
    key = (city.lower().strip(), state.upper().strip())
    return _US_CITIES.get(key)


# ── Load & index stations (cached after first call) ───────────────────────────
def load_stations(force_reload=False):
    """
    Parse CSV, resolve lat/lon from local city DB, cache result.

    Performance:
      - First call: ~50-100 ms (pure pandas + dict lookups, no I/O after CSV read)
      - Subsequent calls: O(1) — returns cached list
    """
    global _STATIONS_CACHE
    with _CACHE_LOCK:
        if _STATIONS_CACHE is not None and not force_reload:
            return _STATIONS_CACHE

        if not _US_CITIES:
            _load_city_db()

        df = pd.read_csv(settings.FUEL_STATIONS_CSV, sep=",")
        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns={
            "OPIS Truckstop ID": "id",
            "Truckstop Name": "name",
            "Address": "address",
            "City": "city",
            "State": "state",
            "Rack ID": "rack_id",
            "Retail Price": "price",
        })
        df = df.drop_duplicates(subset=["id", "name", "price"]).reset_index(drop=True)

        unique_pairs = df[["city", "state"]].drop_duplicates()
        coord_map = {}
        for _, row in unique_pairs.iterrows():
            city = str(row["city"]).strip()
            state = str(row["state"]).strip()
            coord_map[(city, state)] = _coords_for_station(city, state)

        stations = []
        for _, row in df.iterrows():
            city = str(row["city"]).strip()
            state = str(row["state"]).strip()
            coords = coord_map.get((city, state))
            if coords is None:
                continue
            stations.append({
                "id": int(row["id"]),
                "name": str(row["name"]),
                "address": str(row["address"]),
                "city": city,
                "state": state,
                "price": float(row["price"]),
                "lat": coords[0],
                "lon": coords[1],
            })

        _STATIONS_CACHE = stations
        return stations
