"""
Route planning:
  1. Single OSRM call for full route geometry + distance.
  2. Walk the polyline; find stations within a corridor.
  3. fuel-stop selection: go as far as possible, choose cheapest stop.
"""
import math
import requests
from django.conf import settings
from .data import load_stations

METERS_PER_MILE = 1609.344

# station must be within this distance of the polyline
CORRIDOR_MILES = 30


def get_osrm_route(origin_coords, dest_coords):
    """
    One OSRM call. Returns (distance_miles, duration_seconds, polyline).
    polyline is a list of [lon, lat] pairs (GeoJSON order).
    """
    if hasattr(settings, 'OSRM_MOCK_ROUTE') and settings.OSRM_MOCK_ROUTE:
        return settings.OSRM_MOCK_ROUTE

    lat1, lon1 = origin_coords
    lat2, lon2 = dest_coords
    url = (
        f"{settings.OSRM_BASE_URL}/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}"
        "?overview=full&geometries=geojson&steps=false"
    )
    headers = {"User-Agent": "FuelRouteApp/1.0 (fuel-route-planner)"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("OSRM returned no route")

    route = data["routes"][0]
    distance_miles = route["distance"] / METERS_PER_MILE
    duration_seconds = route["duration"]
    coords = route["geometry"]["coordinates"]  # [[lon, lat], ...]
    return distance_miles, duration_seconds, coords


def _cumulative_distances(polyline):
    """Returns list of cumulative miles at each polyline point."""
    cum = [0.0]
    for i in range(1, len(polyline)):
        lon1, lat1 = polyline[i - 1]
        lon2, lat2 = polyline[i]
        cum.append(cum[-1] + _haversine(lat1, lon1, lat2, lon2))
    return cum


def _closest_polyline_point(lat, lon, polyline, cum_dist):
    """
    Returns (idx, mile_mark, dist_miles) of the closest polyline point.
    Assumes polyline points are (lon, lat).
    """
    best_idx = 0
    best_dist = float("inf")

    for i, point in enumerate(polyline):
        p_lon, p_lat = point[0], point[1]  # (lon, lat)
        dist = _haversine(lat, lon, p_lat, p_lon)
        if dist < best_dist:
            best_dist = dist
            best_idx = i

    return best_idx, cum_dist[best_idx], best_dist


def _haversine(lat1, lon1, lat2, lon2):
    """Returns distance in miles between two lat/lon points."""
    R = 3958.8  # Earth radius in miles
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(d_lon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def find_candidate_stations(polyline, cum_dist):
    """
    Returns stations within CORRIDOR_MILES of the route, sorted by mile mark.
    Deduplicates by id (keeps cheapest price).
    Assumes polyline points are (lon, lat).
    """
    stations = load_stations()
    total_miles = cum_dist[-1]

    # polyline is (lon, lat) — index 1 is lat, index 0 is lon
    lats = [p[1] for p in polyline]
    lons = [p[0] for p in polyline]

    avg_lat = sum(lats) / len(lats)
    DEGREE_LAT_PADDING = CORRIDOR_MILES / 69.0
    DEGREE_LON_PADDING = CORRIDOR_MILES / (69.0 * math.cos(math.radians(avg_lat)))

    min_lat = min(lats) - DEGREE_LAT_PADDING
    max_lat = max(lats) + DEGREE_LAT_PADDING
    min_lon = min(lons) - DEGREE_LON_PADDING
    max_lon = max(lons) + DEGREE_LON_PADDING

    nearby = [
        s for s in stations
        if min_lat <= s["lat"] <= max_lat and min_lon <= s["lon"] <= max_lon
    ]
    print(f"Stations after bbox filter: {len(nearby)} / {len(stations)}")

    candidates = []
    for s in nearby:
        idx, mile_mark, dist = _closest_polyline_point(s["lat"], s["lon"], polyline, cum_dist)
        if dist <= CORRIDOR_MILES and 0 < mile_mark < total_miles:
            candidates.append({**s, "mile_mark": mile_mark, "detour_miles": dist})

    # Deduplicate by id, keep cheapest price
    seen = {}
    for c in candidates:
        key = c["id"]
        if key not in seen or c["price"] < seen[key]["price"]:
            seen[key] = c

    return sorted(seen.values(), key=lambda x: x["mile_mark"])


def select_fuel_stops(candidates, total_miles):
    """
    Greedy algorithm:
      - Start at mile 0, full tank (MAX_RANGE miles of fuel).
      - Repeatedly: look ahead within remaining range, pick cheapest station.
      - Must stop before running out of fuel.
    """
    MAX_RANGE = settings.VEHICLE_MAX_RANGE_MILES
    TANK_GALLONS = settings.TANK_CAPACITY_GALLONS
    MPG = settings.VEHICLE_MPG

    current_mile = 0.0
    fuel_remaining = MAX_RANGE  # miles worth of fuel
    stops = []

    while True:
        miles_to_dest = total_miles - current_mile
        if fuel_remaining >= miles_to_dest:
            break  # can reach destination – done

        # All stations reachable from here
        reachable = [
            s for s in candidates
            if current_mile < s["mile_mark"] <= current_mile + fuel_remaining
        ]

        if not reachable:
            stops.append(
                {"warning": f"No reachable station from mile {current_mile:.0f} — route may be outside coverage area."})
            break

        best = min(reachable, key=lambda s: s["price"])
        gallons_purchased = TANK_GALLONS  # fill up completely
        cost = round(gallons_purchased * best["price"], 2)

        stops.append({
            "station_id": best["id"],
            "name": best["name"],
            "address": best["address"],
            "city": best["city"],
            "state": best["state"],
            "price_per_gallon": round(best["price"], 4),
            "gallons_purchased": gallons_purchased,
            "cost_usd": cost,
            "mile_mark": round(best["mile_mark"], 1),
            "detour_miles": round(best["detour_miles"], 1),
            "lat": best["lat"],
            "lon": best["lon"],
        })

        fuel_remaining = MAX_RANGE - (best["mile_mark"] - current_mile) + MAX_RANGE
        fuel_remaining = MAX_RANGE  # simplified: fill to full
        current_mile = best["mile_mark"]

    return stops


def compute_total_cost(stops, total_miles):
    """Sum all stop costs. Also returns total gallons burned for the trip."""
    total_gallons = round(total_miles / settings.VEHICLE_MPG, 2)
    total_cost = round(sum(s.get("cost_usd", 0) for s in stops if "warning" not in s), 2)
    return total_cost, total_gallons
