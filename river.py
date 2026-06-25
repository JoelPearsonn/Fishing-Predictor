import requests


def get_river_data(lat, lon):
    try:
        stations_url = "https://environment.data.gov.uk/flood-monitoring/id/stations"

        station_params = {
            "lat": lat,
            "long": lon,
            "dist": 15,
            "parameter": "level",
        }

        station_response = requests.get(stations_url, params=station_params, timeout=10)
        station_data = station_response.json()

        stations = station_data.get("items", [])

        if not stations:
            return {
                "river_score": 6.5,
                "reasons": ["No nearby river gauge found. Using neutral river score."],
            }

        station = stations[0]

        station_name = station.get("label", "Unknown station")
        river_name = station.get("riverName", "Unknown river")
        measures = station.get("measures", [])

        if not measures:
            return {
                "river_score": 6.5,
                "reasons": [f"Found {station_name}, but no level readings available."],
            }

        measure_id = measures[0]["@id"]

        readings_url = f"{measure_id}/readings"

        readings_params = {
            "_sorted": "",
            "_limit": 24,
        }

        readings_response = requests.get(readings_url, params=readings_params, timeout=10)
        readings_data = readings_response.json()

        readings = readings_data.get("items", [])

        if len(readings) < 2:
            return {
                "river_score": 6.5,
                "reasons": [f"Not enough recent readings for {station_name}."],
            }

        latest = readings[0]
        oldest = readings[-1]

        latest_level = latest.get("value")
        oldest_level = oldest.get("value")

        if latest_level is None or oldest_level is None:
            return {
                "river_score": 6.5,
                "reasons": [f"River readings found for {station_name}, but values were missing."],
            }

        change_m = latest_level - oldest_level
        change_cm = change_m * 100

        score = 6.5

        if 5 <= change_cm <= 30:
            score = 9
        elif 0 < change_cm < 5:
            score = 7.5
        elif -20 <= change_cm <= 0:
            score = 8
        elif change_cm > 30:
            score = 5
        elif change_cm < -20:
            score = 6

        return {
            "river_score": round(score, 1),
            "station_name": station_name,
            "river_name": river_name,
            "latest_level": latest_level,
            "change_cm": round(change_cm, 1),
            "reasons": [
                f"Nearest river gauge: {station_name}",
                f"River: {river_name}",
                f"Latest river level: {latest_level}m",
                f"Recent level change: {round(change_cm, 1)}cm",
                f"River score calculated as {round(score, 1)}/10",
            ],
        }

    except Exception as error:
        return {
            "river_score": 6.5,
            "reasons": [f"Could not fetch river data: {error}"],
        }