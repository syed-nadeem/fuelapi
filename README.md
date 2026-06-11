# Fuel Route Planner API

A Django REST API that computes an optimal (cost-effective) fueling plan for a road trip across the USA.



## Setup

```bash
pip install -r requirements.txt
python manage.py runserver
```

No database migrations needed.
Using Leaflet.js for FE map

### Plan a route API

```
POST /api/route/
Content-Type: application/json

{
  "start": "Dallas, TX",
  "end":   "Chicago, IL"
}
```

### Example response

```json
{
  "origin": {
    "query": "Dallas, TX",
    "lat": 32.78,
    "lon": -96.79
  },
  "destination": {
    "query": "Chicago, IL",
    "lat": 41.85,
    "lon": -87.65
  },
  "route": {
    "type": "LineString",
    "coordinates": [
      [
        ...
      ],
      ...
    ],
    "distance_miles": 921.3,
    "duration_hours": 13.6
  },
  "fuel_stops": [
    {
      "station_id": 7,
      "name": "WOODSHED OF BIG CABIN",
      "address": "I-44, EXIT 283 & US-69",
      "city": "Big Cabin",
      "state": "OK",
      "price_per_gallon": 3.0073,
      "gallons_purchased": 50.0,
      "cost_usd": 150.37,
      "mile_mark": 248.1,
      "detour_miles": 4.2,
      "lat": 36.54,
      "lon": -95.07
    }
  ],
  "summary": {
    "total_distance_miles": 921.3,
    "total_gallons_burned": 92.13,
    "total_fuel_cost_usd": 300.74,
    "vehicle_mpg": 10,
    "vehicle_max_range_miles": 500,
    "num_fuel_stops": 2
  }
}
```

### Station geocoding
Each station's city+state is geocoded via Nominatim once on first request and cached in memory for all subsequent
requests.

### Station filtering
The full OSRM route polyline is walked; any station within **30 miles** of any polyline point is considered a candidate.

### Cost calculation
`gallons = tank_capacity (50)` per fill-up · `price_per_gallon`.
Total trip gallons burned = `total_miles / mpg` (10 mpg).

## External APIs used (Free)
**Total external API calls per request: 3**
2 for geocoding start and end location
1 for routing
[Nominatim](https://nominatim.openstreetmap.org) --> Geocoding start/end
[OSRM](http://router.project-osrm.org) --> Driving route + polyline

## demo
Visit `http://localhost:8000/` for demo.
