import json
from django.test import TestCase, override_settings
from api.routing import _haversine

_MOCK_POLYLINE = [
    [-96.79, 32.78],
    [-97.61, 30.82],
    [-95.07, 36.54],
    [-94.40, 35.39],
    [-89.00, 40.00],
    [-87.65, 41.85],
]
_MOCK_DIST_MILES = 960.0
_MOCK_DURATION = 50400

_GEOCODE_OVERRIDE = {
    "dallas": (32.7797, -96.7897),
    "chicago": (41.8500, -87.6500),
}


@override_settings(
    OSRM_MOCK_ROUTE=(_MOCK_DIST_MILES, _MOCK_DURATION, _MOCK_POLYLINE),
    GEOCODE_OVERRIDE=_GEOCODE_OVERRIDE,
)
class RouteAPITests(TestCase):

    def _post(self, body):
        return self.client.post("/api/route/", data=json.dumps(body), content_type="application/json")

    def test_valid_route_returns_200(self):
        resp = self._post({"start": "Dallas, TX", "end": "Chicago, IL"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("route", data)
        self.assertIn("fuel_stops", data)
        self.assertIn("summary", data)

    def test_route_distance_populated(self):
        data = self._post({"start": "Dallas, TX", "end": "Chicago, IL"}).json()
        self.assertAlmostEqual(data["route"]["distance_miles"], _MOCK_DIST_MILES, delta=1)

    def test_route_has_coordinates(self):
        coords = self._post({"start": "Dallas, TX", "end": "Chicago, IL"}).json()["route"]["coordinates"]
        self.assertIsInstance(coords, list)
        self.assertGreater(len(coords), 2)

    def test_fuel_stops_are_ordered(self):
        stops = [s for s in self._post({"start": "Dallas, TX", "end": "Chicago, IL"}).json()["fuel_stops"] if
                 "warning" not in s]
        miles = [s["mile_mark"] for s in stops]
        self.assertEqual(miles, sorted(miles))

    def test_fuel_stops_within_max_range(self):
        from django.conf import settings
        stops = [s for s in self._post({"start": "Dallas, TX", "end": "Chicago, IL"}).json()["fuel_stops"] if
                 "warning" not in s]
        prev = 0.0
        for s in stops:
            self.assertLessEqual(s["mile_mark"] - prev, settings.VEHICLE_MAX_RANGE_MILES + 0.1)
            prev = s["mile_mark"]

    def test_summary_required_fields(self):
        summary = self._post({"start": "Dallas, TX", "end": "Chicago, IL"}).json()["summary"]
        for f in ("total_distance_miles", "total_gallons_burned", "total_fuel_cost_usd", "num_fuel_stops"):
            self.assertIn(f, summary)

    def test_fuel_cost_positive(self):
        cost = self._post({"start": "Dallas, TX", "end": "Chicago, IL"}).json()["summary"]["total_fuel_cost_usd"]
        self.assertGreater(cost, 0)

    def test_stops_have_lat_lon(self):
        stops = [s for s in self._post({"start": "Dallas, TX", "end": "Chicago, IL"}).json()["fuel_stops"] if
                 "warning" not in s]
        for s in stops:
            self.assertTrue(-90 <= s["lat"] <= 90)
            self.assertTrue(-180 <= s["lon"] <= 180)

    def test_mpg_gallons_consistent(self):
        from django.conf import settings
        s = self._post({"start": "Dallas, TX", "end": "Chicago, IL"}).json()["summary"]
        self.assertAlmostEqual(s["total_gallons_burned"], s["total_distance_miles"] / settings.VEHICLE_MPG, delta=0.1)

    def test_missing_start_400(self):
        self.assertEqual(self._post({"end": "Chicago, IL"}).status_code, 400)

    def test_missing_end_400(self):
        self.assertEqual(self._post({"start": "Dallas, TX"}).status_code, 400)

    def test_empty_body_400(self):
        self.assertEqual(self._post({}).status_code, 400)

    def test_unknown_location_400(self):
        self.assertEqual(self._post({"start": "ZZZ Nowhere Real", "end": "Chicago, IL"}).status_code, 400)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get("/api/route/").status_code, 405)

    def test_haversine_known_distance(self):
        d = _haversine(32.78, -96.79, 41.85, -87.65)
        self.assertAlmostEqual(d, 802, delta=30)

    def test_cumulative_distances_monotonic(self):
        from api.routing import _cumulative_distances
        cum = _cumulative_distances(_MOCK_POLYLINE)
        self.assertEqual(cum[0], 0.0)
        for i in range(1, len(cum)):
            self.assertGreater(cum[i], cum[i - 1])

    def test_cheapest_stop_selected_first(self):
        from api.routing import _cumulative_distances, find_candidate_stations, select_fuel_stops
        cum = _cumulative_distances(_MOCK_POLYLINE)
        candidates = find_candidate_stations(_MOCK_POLYLINE, cum)
        stops = select_fuel_stops(candidates, _MOCK_DIST_MILES)
        first_reachable = [c for c in candidates if c["mile_mark"] <= 500]
        if first_reachable and stops and "warning" not in stops[0]:
            cheapest = min(first_reachable, key=lambda x: x["price"])
            self.assertEqual(stops[0]["station_id"], cheapest["id"])
