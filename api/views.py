from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from .serializers import RouteRequestSerializer

from .data import geocode
from .routing import (
    get_osrm_route,
    _cumulative_distances,
    find_candidate_stations,
    select_fuel_stops,
    compute_total_cost,
)


class RouteView(APIView):
    @swagger_auto_schema(
        operation_description="Calculate route",
        request_body=RouteRequestSerializer
    )
    def post(self, request):
        """
        :title: Calculate Route and Fuel Stops
        :path: /api/route/
        :method: POST
        :description: Calculate the driving route between two locations and determine optimal fuel stops
        and the journey based on vehicle range and fuel prices.

        :arg start: REQUIRED|string Starting location. Example: "Dallas, TX"
        :arg end: REQUIRED|string Destination location. Example: "Chicago, IL"

        :return: Returns route information, fuel stop recommendations, and trip cost summary.

        :return_data origin: object Origin location details.
        :return_data destination: object Destination location details.
        :return_data route: object Route geometry, distance, and duration.
        :return_data fuel_stops: array Recommended fuel stops along the route.
        :return_data summary: object Trip summary and fuel cost calculations.

        :example_request: {
            "start": "Big Cabin, OK",
            "end": "Tomah, WI"
        }

        :example_response: {
            "origin": {
                "query": "Big Cabin, OK",
                "lat": 32.7767,
                "lon": -96.7970
            },
            "destination": {
                "query": "Tomah, WI",
                "lat": 41.8781,
                "lon": -87.6298
            },
            "route": {
                "type": "LineString",
                "coordinates": [
                    [-96.7970, 32.7767],
                    [-87.6298, 41.8781]
                ],
                "distance_miles": 968.4,
                "duration_hours": 14.82
            },
            "fuel_stops": [
                {
                    "station_name": "Example Fuel Station",
                    "city": "Springfield",
                    "state": "IL",
                    "price_per_gallon": 3.29,
                    "gallons": 12.5,
                    "cost": 41.13
                }
            ],
            "summary": {
                "total_distance_miles": 968.4,
                "total_gallons_burned": 38.7,
                "total_fuel_cost_usd": 127.35,
                "vehicle_mpg": 25,
                "vehicle_max_range_miles": 500,
                "num_fuel_stops": 2
            }
        }
        """

        serializer = RouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        start_str = serializer.validated_data["start"]
        end_str = serializer.validated_data["end"]

        try:
            origin = geocode(start_str)
        except Exception as e:
            return Response({"error": f"Could not geocode start location: {e}"}, status=400)
        if origin is None:
            return Response({"error": f"Location not found: '{start_str}'"}, status=400)

        try:
            destination = geocode(end_str)
        except Exception as e:
            return Response({"error": f"Could not geocode end location: {e}"}, status=400)
        if destination is None:
            return Response({"error": f"Location not found: '{end_str}'"}, status=400)

        # OSRM route call
        try:
            distance_miles, duration_sec, polyline = get_osrm_route(origin, destination)
        except Exception as e:
            return Response({"error": f"Routing service error: {e}"}, status=502)

        # Local computation for route
        cum_dist = _cumulative_distances(polyline)
        candidates = find_candidate_stations(polyline, cum_dist)
        stops = select_fuel_stops(candidates, distance_miles)
        total_cost, total_gallons = compute_total_cost(stops, distance_miles)

        # Thin polyline for response payload (max 500 points)
        step = max(1, len(polyline) // 500)
        thinned = polyline[::step]
        if polyline and thinned[-1] != polyline[-1]:
            thinned.append(polyline[-1])

        return Response({
            "origin": {
                "query": start_str,
                "lat": origin[0],
                "lon": origin[1],
            },
            "destination": {
                "query": end_str,
                "lat": destination[0],
                "lon": destination[1],
            },
            "route": {
                "type": "LineString",
                "coordinates": thinned,
                "distance_miles": round(distance_miles, 1),
                "duration_hours": round(duration_sec / 3600, 2),
            },
            "fuel_stops": stops,
            "summary": {
                "total_distance_miles": round(distance_miles, 1),
                "total_gallons_burned": total_gallons,
                "total_fuel_cost_usd": total_cost,
                "vehicle_mpg": settings.VEHICLE_MPG,
                "vehicle_max_range_miles": settings.VEHICLE_MAX_RANGE_MILES,
                "num_fuel_stops": len([s for s in stops if "warning" not in s]),
            },
        })
