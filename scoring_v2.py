from species_profiles import SPECIES_PROFILES
from location_profiles import LOCATION_PROFILES


SCORING_MODEL_VERSION = "v2.1 venue-confidence"


SPECIES_FACTOR_WEIGHTS = {
    "Bass": {
        "season": 0.12,
        "time": 0.16,
        "location": 0.16,
        "water_movement": 0.18,
        "clarity": 0.14,
        "temperature": 0.07,
        "wind": 0.09,
        "pressure": 0.04,
        "rainfall": 0.04,
    },
    "Sea Trout": {
        "season": 0.12,
        "time": 0.18,
        "location": 0.14,
        "water_movement": 0.20,
        "clarity": 0.18,
        "temperature": 0.07,
        "wind": 0.04,
        "pressure": 0.03,
        "rainfall": 0.04,
    },
    "Flounder": {
        "season": 0.12,
        "time": 0.08,
        "location": 0.16,
        "water_movement": 0.24,
        "clarity": 0.14,
        "temperature": 0.07,
        "wind": 0.05,
        "pressure": 0.04,
        "rainfall": 0.10,
    },
    "Mullet": {
        "season": 0.16,
        "time": 0.14,
        "location": 0.16,
        "water_movement": 0.06,
        "clarity": 0.20,
        "temperature": 0.13,
        "wind": 0.09,
        "pressure": 0.04,
        "rainfall": 0.02,
    },
    "Pike": {
        "season": 0.14,
        "time": 0.12,
        "location": 0.22,
        "water_movement": 0.03,
        "clarity": 0.10,
        "temperature": 0.18,
        "wind": 0.10,
        "pressure": 0.07,
        "rainfall": 0.04,
    },
    "Perch": {
        "season": 0.14,
        "time": 0.12,
        "location": 0.22,
        "water_movement": 0.03,
        "clarity": 0.12,
        "temperature": 0.16,
        "wind": 0.08,
        "pressure": 0.05,
        "rainfall": 0.08,
    },
    "Roach": {
        "season": 0.14,
        "time": 0.10,
        "location": 0.22,
        "water_movement": 0.03,
        "clarity": 0.14,
        "temperature": 0.14,
        "wind": 0.07,
        "pressure": 0.07,
        "rainfall": 0.09,
    },
    "Bream": {
        "season": 0.14,
        "time": 0.10,
        "location": 0.22,
        "water_movement": 0.03,
        "clarity": 0.12,
        "temperature": 0.14,
        "wind": 0.07,
        "pressure": 0.07,
        "rainfall": 0.11,
    },
    "Carp": {
        "season": 0.14,
        "time": 0.12,
        "location": 0.22,
        "water_movement": 0.03,
        "clarity": 0.10,
        "temperature": 0.18,
        "wind": 0.07,
        "pressure": 0.05,
        "rainfall": 0.09,
    },
    "Tench": {
        "season": 0.16,
        "time": 0.16,
        "location": 0.24,
        "water_movement": 0.03,
        "clarity": 0.12,
        "temperature": 0.16,
        "wind": 0.05,
        "pressure": 0.04,
        "rainfall": 0.04,
    },
}


DEFAULT_WEIGHTS = {
    "season": 0.14,
    "time": 0.12,
    "location": 0.18,
    "water_movement": 0.10,
    "clarity": 0.14,
    "temperature": 0.12,
    "wind": 0.08,
    "pressure": 0.06,
    "rainfall": 0.06,
}


def clamp(value):
    return max(0, min(10, value))


def get_time_period(selected_time):
    hour = selected_time.hour

    if 4 <= hour < 8:
        return "dawn"
    if 8 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "day"
    if 17 <= hour < 22:
        return "dusk"

    return "night"


def make_factor(score, confidence, reason):
    return {
        "score": round(clamp(score), 1),
        "confidence": confidence,
        "reason": reason,
    }


def score_range(value, ideal_range, soft_margin, label, unit):
    if value is None:
        return 6, "Low", f"{label} data unavailable, so V2 scored it neutral."

    low, high = ideal_range

    if low <= value <= high:
        return 8.5, "High", f"{label} is {value}{unit}, inside the preferred range of {low}–{high}{unit}."

    if low - soft_margin <= value < low:
        return 6.5, "Medium", f"{label} is {value}{unit}, slightly below the preferred range."

    if high < value <= high + soft_margin:
        return 6.5, "Medium", f"{label} is {value}{unit}, slightly above the preferred range."

    return 4.5, "Medium", f"{label} is {value}{unit}, outside the preferred range."


def factor_season(species, selected_date):
    profile = SPECIES_PROFILES[species]
    month = selected_date.month

    if month in profile["best_months"]:
        return make_factor(9, "High", f"{month} is within the main season for {species}.")

    shoulder_months = []

    for m in profile["best_months"]:
        shoulder_months.extend([m - 1, m + 1])

    shoulder_months = [(m - 1) % 12 + 1 for m in shoulder_months]

    if month in shoulder_months:
        return make_factor(6.5, "Medium", f"{month} is close to the main season for {species}.")

    return make_factor(4.5, "High", f"{month} is outside the main season for {species}.")


def factor_time(species, selected_time):
    profile = SPECIES_PROFILES[species]
    period = get_time_period(selected_time)

    if period in profile["good_times"]:
        return make_factor(9, "High", f"{period.title()} is a strong feeding window for {species}.")

    if species in ["Pike", "Perch", "Roach", "Bream", "Carp", "Tench"] and period == "day":
        return make_factor(6.5, "Medium", f"Daytime is workable for {species}, but not always peak.")

    return make_factor(5, "Medium", f"{period.title()} is not a peak time for {species}.")


def factor_location(location, species, location_info):
    location_profile = LOCATION_PROFILES.get(location)

    if not location_profile:
        return make_factor(
            5,
            "Low",
            f"No location profile exists for {location}, so location suitability is neutral.",
        )

    species_confidence = location_profile.get("species_confidence", {})
    confidence_score = species_confidence.get(species)

    if confidence_score is None:
        return make_factor(
            3,
            "High",
            f"{species} is not listed as a known target species at {location}.",
        )

    if confidence_score >= 8:
        confidence = "High"
        wording = "strong"
    elif confidence_score >= 6:
        confidence = "Medium"
        wording = "reasonable"
    else:
        confidence = "Medium"
        wording = "weak / lower-confidence"

    return make_factor(
        confidence_score,
        confidence,
        f"{location} profile: {wording} venue/species match for {species}. {location_profile['description']}",
    )


def factor_temperature(species, weather_data):
    profile = SPECIES_PROFILES[species]

    score, confidence, reason = score_range(
        weather_data.get("temperature"),
        profile["temperature_range"],
        4,
        "Air temperature",
        "°C",
    )

    return make_factor(score, confidence, reason)


def factor_wind(species, weather_data):
    profile = SPECIES_PROFILES[species]

    wind_speed = weather_data.get("wind")
    wind_direction = weather_data.get("wind_direction")

    speed_score, confidence, speed_reason = score_range(
        wind_speed,
        profile["wind_speed_range"],
        8,
        "Wind speed",
        "km/h",
    )

    direction_adjustment = 0
    direction_reason = "Wind direction unavailable."

    if wind_direction:
        if wind_direction in profile.get("good_wind_directions", []):
            direction_adjustment = 1
            direction_reason = f"{wind_direction} wind is favourable for {species}."
        elif wind_direction in profile.get("bad_wind_directions", []):
            direction_adjustment = -1.5
            direction_reason = f"{wind_direction} wind is less favourable for {species}."
        else:
            direction_reason = f"{wind_direction} wind is neutral for {species}."

    return make_factor(speed_score + direction_adjustment, confidence, f"{speed_reason} {direction_reason}")


def factor_pressure(species, weather_data):
    profile = SPECIES_PROFILES[species]

    score, confidence, reason = score_range(
        weather_data.get("pressure"),
        profile["pressure_range"],
        7,
        "Pressure",
        "hPa",
    )

    return make_factor(score, confidence, reason)


def factor_rainfall(species, weather_data):
    rain_24h = weather_data.get("rain_24h", 0) or 0
    rain_72h = weather_data.get("rain_72h", 0) or 0

    if species in ["Sea Trout", "Salmon"]:
        if 3 <= rain_72h <= 25:
            return make_factor(8.5, "Medium", "Recent rain may give useful water and movement for migratory fish.")
        if rain_72h > 35:
            return make_factor(4, "Medium", "Heavy recent rain may make water too high or coloured.")
        return make_factor(5.5, "Medium", "Limited recent rain may mean less movement for migratory fish.")

    if species == "Mullet":
        if rain_72h <= 5:
            return make_factor(8, "Medium", "Low recent rain should help keep water clearer for mullet.")
        return make_factor(4.5, "Medium", "Recent rain may reduce clarity for mullet.")

    if species in ["Bream", "Roach", "Carp", "Tench", "Perch"]:
        if rain_24h <= 8:
            return make_factor(7, "Medium", "Recent rainfall should not overly disturb the stillwater.")
        return make_factor(5, "Medium", "Recent rain may cool or colour the margins.")

    if species == "Pike":
        if rain_72h <= 20:
            return make_factor(7, "Medium", "Rainfall looks workable for pike.")
        return make_factor(5, "Medium", "Heavy rain may reduce visibility for lure fishing.")

    return make_factor(6.5, "Low", "Rainfall scored as broadly neutral.")


def factor_clarity(species, weather_data, river_data):
    profile = SPECIES_PROFILES[species]
    clarity = profile["clarity"]

    rain_72h = weather_data.get("rain_72h", 0) or 0
    river_change = 0

    if river_data:
        river_change = river_data.get("change_cm", 0) or 0

    if clarity == "clear":
        if rain_72h < 5 and abs(river_change) < 10:
            return make_factor(8.5, "Medium", "Water is likely clear, which suits this species.")
        return make_factor(4.5, "Medium", "Water may be too coloured for this species.")

    if clarity == "slightly_coloured":
        if 2 <= rain_72h <= 20:
            return make_factor(8.5, "Medium", "Recent rain may create useful colour without making water too dirty.")
        if rain_72h > 30:
            return make_factor(4.5, "Medium", "Water may be too coloured.")
        return make_factor(6.5, "Medium", "Water clarity is likely neutral.")

    if clarity == "clear_to_slight_colour":
        if rain_72h <= 15 and river_change <= 20:
            return make_factor(8, "Medium", "Water is likely clear to slightly coloured.")
        if rain_72h > 25 or river_change > 30:
            return make_factor(4.5, "Medium", "Water may be too coloured or unsettled.")
        return make_factor(6.5, "Medium", "Water clarity looks workable.")

    if clarity == "falling_and_clearing":
        if -20 <= river_change <= 0 and rain_72h <= 25:
            return make_factor(9, "Medium", "River appears likely to be falling/clearing, which strongly suits this species.")
        if 0 < river_change <= 25:
            return make_factor(7.5, "Medium", "River has some lift, which can help fish movement.")
        return make_factor(5.5, "Medium", "River clarity/trend is not clearly ideal.")

    return make_factor(6, "Low", "No clear clarity rule exists for this species.")


def factor_water_movement(species, location_info, tide_data, river_data):
    location_type = location_info["type"]

    if location_type == "estuary":
        if tide_data:
            tide_score = tide_data.get("tide_score", 6.5)
            tide_phase = tide_data.get("tide_phase", "unknown tide stage")
            return make_factor(tide_score, "Medium", f"Tide/water movement stage: {tide_phase}.")
        return make_factor(3.5, "Low", "Tide data unavailable for tidal venue.")

    if location_type == "river":
        if river_data:
            river_score = river_data.get("river_score", 6.5)
            return make_factor(river_score, "Medium", "River movement/level score carried into V2.")
        return make_factor(6, "Low", "River data unavailable.")

    if species in ["Pike", "Perch", "Roach", "Bream", "Carp", "Tench", "Rainbow Trout"]:
        return make_factor(6.5, "Low", "Stillwater venue: water movement is less important than location, temperature and wind.")

    return make_factor(6, "Low", "Water movement scored neutral.")


def build_v2_summary(v2_score, old_score, factors):
    diff = round(v2_score - old_score, 1)

    sorted_factors = sorted(
        factors.items(),
        key=lambda item: item[1]["score"],
        reverse=True,
    )

    strongest = sorted_factors[:3]
    weakest = sorted_factors[-3:]

    if diff > 0.4:
        comparison = f"V2 scores this {diff} points higher because it gives more emphasis to the strongest evidence factors."
    elif diff < -0.4:
        comparison = f"V2 scores this {abs(diff)} points lower because it is stricter on the highest-impact factors."
    else:
        comparison = "V2 is broadly aligned with the old score."

    return {
        "comparison": comparison,
        "strongest": [f"{name}: {data['score']}/10 — {data['reason']}" for name, data in strongest],
        "weakest": [f"{name}: {data['score']}/10 — {data['reason']}" for name, data in weakest],
    }


def calculate_score_v2(location, species, selected_date, selected_time, location_info, base_result):
    weather_data = base_result["weather_data"]
    river_data = base_result["river_data"]
    tide_data = base_result["tide_data"]

    weights = SPECIES_FACTOR_WEIGHTS.get(species, DEFAULT_WEIGHTS)

    factors = {
        "season": factor_season(species, selected_date),
        "time": factor_time(species, selected_time),
        "location": factor_location(location, species, location_info),
        "water_movement": factor_water_movement(species, location_info, tide_data, river_data),
        "clarity": factor_clarity(species, weather_data, river_data),
        "temperature": factor_temperature(species, weather_data),
        "wind": factor_wind(species, weather_data),
        "pressure": factor_pressure(species, weather_data),
        "rainfall": factor_rainfall(species, weather_data),
    }

    final_score = 0

    for factor_name, factor_data in factors.items():
        final_score += factor_data["score"] * weights.get(factor_name, 0)

    final_score = round(clamp(final_score), 1)

    return {
        "model_version": SCORING_MODEL_VERSION,
        "score": final_score,
        "weights": weights,
        "factors": factors,
        "summary": build_v2_summary(final_score, base_result["score"], factors),
    }