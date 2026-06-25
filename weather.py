import requests
from datetime import timedelta


def degrees_to_compass(degrees):
    if degrees is None:
        return None

    directions = [
        "N", "NE", "E", "SE",
        "S", "SW", "W", "NW",
    ]

    index = round(degrees / 45) % 8
    return directions[index]


def get_weather(lat, lon, selected_date, selected_time):
    forecast_url = "https://api.open-meteo.com/v1/forecast"

    forecast_params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,cloud_cover,wind_speed_10m,wind_direction_10m,surface_pressure",
        "timezone": "Europe/London",
        "forecast_days": 7,
    }

    try:
        forecast_response = requests.get(forecast_url, params=forecast_params, timeout=10)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()

        target_time = f"{selected_date}T{selected_time.hour:02d}:00"
        times = forecast_data["hourly"]["time"]

        if target_time not in times:
            return empty_weather("Could not find weather for that exact hour.")

        index = times.index(target_time)

        temp = forecast_data["hourly"]["temperature_2m"][index]
        rain = forecast_data["hourly"]["precipitation"][index]
        cloud = forecast_data["hourly"]["cloud_cover"][index]
        wind = forecast_data["hourly"]["wind_speed_10m"][index]
        wind_degrees = forecast_data["hourly"]["wind_direction_10m"][index]
        wind_direction = degrees_to_compass(wind_degrees)
        pressure = forecast_data["hourly"]["surface_pressure"][index]

        rainfall_history = get_recent_rainfall(lat, lon, selected_date)

        return {
            "weather_score": 5,
            "temperature": temp,
            "rain": rain,
            "cloud": cloud,
            "wind": wind,
            "wind_direction": wind_direction,
            "wind_degrees": wind_degrees,
            "pressure": pressure,
            "rain_24h": rainfall_history["rain_24h"],
            "rain_72h": rainfall_history["rain_72h"],
            "rain_7d": rainfall_history["rain_7d"],
            "reasons": [
                f"Temperature: {temp}°C",
                f"Rain forecast at selected hour: {rain} mm",
                f"Cloud cover: {cloud}%",
                f"Wind speed: {wind} km/h",
                f"Wind direction: {wind_direction} ({wind_degrees}°)",
                f"Pressure: {pressure} hPa",
                f"Rainfall last 24h: {rainfall_history['rain_24h']} mm",
                f"Rainfall last 72h: {rainfall_history['rain_72h']} mm",
                f"Rainfall last 7 days: {rainfall_history['rain_7d']} mm",
            ],
        }

    except Exception as e:
        return empty_weather(f"Weather API error: {e}")


def empty_weather(reason):
    return {
        "weather_score": 5,
        "temperature": None,
        "rain": None,
        "cloud": None,
        "wind": None,
        "wind_direction": None,
        "wind_degrees": None,
        "pressure": None,
        "rain_24h": 0,
        "rain_72h": 0,
        "rain_7d": 0,
        "reasons": [reason],
    }


def get_recent_rainfall(lat, lon, selected_date):
    archive_url = "https://archive-api.open-meteo.com/v1/archive"

    start_date = selected_date - timedelta(days=7)
    end_date = selected_date - timedelta(days=1)

    archive_params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "daily": "precipitation_sum",
        "timezone": "Europe/London",
    }

    try:
        archive_response = requests.get(archive_url, params=archive_params, timeout=10)
        archive_response.raise_for_status()
        archive_data = archive_response.json()

        rain_values = archive_data["daily"]["precipitation_sum"]

        return {
            "rain_24h": round(sum(rain_values[-1:]), 1),
            "rain_72h": round(sum(rain_values[-3:]), 1),
            "rain_7d": round(sum(rain_values[-7:]), 1),
        }

    except Exception:
        return {
            "rain_24h": 0,
            "rain_72h": 0,
            "rain_7d": 0,
        }