from species_profiles import SPECIES_PROFILES
from weather import get_weather
from river import get_river_data
from tides import get_tide_data


WEIGHTS = {
    "season": 0.15,
    "time": 0.15,
    "location": 0.15,
    "weather": 0.20,
    "pressure": 0.10,
    "water": 0.15,
    "clarity": 0.10,
}


def clamp_score(score):
    return max(0, min(10, score))


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


def in_range(value, preferred_range):
    if value is None:
        return False

    low, high = preferred_range
    return low <= value <= high


def distance_from_range(value, preferred_range):
    if value is None:
        return 0

    low, high = preferred_range

    if value < low:
        return low - value
    if value > high:
        return value - high

    return 0


def make_component(name, score, explanation, positives=None, negatives=None, neutrals=None):
    return {
        "name": name,
        "score": round(clamp_score(score), 1),
        "explanation": explanation,
        "positives": positives or [],
        "negatives": negatives or [],
        "neutrals": neutrals or [],
    }


def score_range_component(value, preferred_range, name, unit, ideal_text, bad_text):
    if value is None:
        return 6, [f"{name} data unavailable."], [], []

    if in_range(value, preferred_range):
        return 8, [], [f"{name} is {value}{unit}, which is inside the preferred range of {preferred_range[0]}–{preferred_range[1]}{unit}. {ideal_text}"], []

    distance = distance_from_range(value, preferred_range)

    if distance <= 5:
        return 6.5, [], [], [f"{name} is {value}{unit}, slightly outside the ideal range but still workable."]

    return 4.5, [], [], [f"{name} is {value}{unit}. {bad_text}"]


def score_season(species, selected_date):
    profile = SPECIES_PROFILES[species]
    month = selected_date.month

    if month in profile["best_months"]:
        return make_component(
            "Season",
            9,
            f"{species} is in a strong seasonal window.",
            positives=[f"Month {month} is one of the best months for {species}."],
        )

    return make_component(
        "Season",
        5,
        f"{species} is outside its strongest seasonal window.",
        negatives=[f"Month {month} is not listed as a peak month for {species}."],
    )


def score_time(species, selected_time):
    profile = SPECIES_PROFILES[species]
    period = get_time_period(selected_time)

    if period in profile["good_times"]:
        return make_component(
            "Time",
            9,
            f"{period.title()} is a good feeding window for {species}.",
            positives=[f"{species} often feed better around {period}."],
        )

    return make_component(
        "Time",
        5,
        f"{period.title()} is not the strongest feeding window for {species}.",
        negatives=[f"The selected time falls into {period}, which is not ideal for {species}."],
    )


def score_weather_for_species(species, weather_data):
    profile = SPECIES_PROFILES[species]

    cloud = weather_data.get("cloud")
    rain = weather_data.get("rain")
    wind = weather_data.get("wind")
    wind_direction = weather_data.get("wind_direction")
    temp = weather_data.get("temperature")

    positives = []
    negatives = []
    neutrals = []

    cloud_score, cloud_neutral, cloud_positive, cloud_negative = score_range_component(
        cloud,
        profile["cloud_range"],
        "Cloud cover",
        "%",
        "This suits the light level this species usually prefers.",
        "The light level is not ideal for this species.",
    )

    rain_score, rain_neutral, rain_positive, rain_negative = score_range_component(
        rain,
        profile["rain_range"],
        "Rain",
        "mm",
        "This amount of rain is useful rather than disruptive.",
        "Rainfall is outside the preferred range.",
    )

    wind_score, wind_neutral, wind_positive, wind_negative = score_range_component(
        wind,
        profile["wind_speed_range"],
        "Wind speed",
        "km/h",
        "This should create useful water movement/ripple without making fishing too hard.",
        "Wind may be too flat or too strong.",
    )

    temp_score, temp_neutral, temp_positive, temp_negative = score_range_component(
        temp,
        profile["temperature_range"],
        "Temperature",
        "°C",
        "This is a good temperature range for activity.",
        "Temperature is outside the preferred range.",
    )

    sub_scores = [cloud_score, rain_score, wind_score, temp_score]
    score = sum(sub_scores) / len(sub_scores)

    positives.extend(cloud_positive + rain_positive + wind_positive + temp_positive)
    negatives.extend(cloud_negative + rain_negative + wind_negative + temp_negative)
    neutrals.extend(cloud_neutral + rain_neutral + wind_neutral + temp_neutral)

    if wind_direction is None:
        neutrals.append("Wind direction unavailable.")
    elif wind_direction in profile.get("good_wind_directions", []):
        score += 1
        positives.append(f"{wind_direction} wind direction suits {species}.")
    elif wind_direction in profile.get("bad_wind_directions", []):
        score -= 1.5
        negatives.append(f"{wind_direction} wind direction is less favourable for {species}.")
    else:
        neutrals.append(f"Wind direction is {wind_direction}, which is neutral for {species}.")

    return make_component(
        "Weather",
        score,
        f"Weather conditions score {round(clamp_score(score), 1)}/10 for {species}.",
        positives=positives,
        negatives=negatives,
        neutrals=neutrals,
    )


def score_pressure(species, weather_data):
    profile = SPECIES_PROFILES[species]
    pressure = weather_data.get("pressure")

    score, neutrals, positives, negatives = score_range_component(
        pressure,
        profile["pressure_range"],
        "Pressure",
        "hPa",
        "Pressure is in this species' preferred range.",
        "Pressure is outside the preferred range.",
    )

    return make_component(
        "Pressure",
        score,
        f"Pressure score is {round(score, 1)}/10.",
        positives=positives,
        negatives=negatives,
        neutrals=neutrals,
    )


def score_clarity(location_type, species, weather_data, river_data):
    profile = SPECIES_PROFILES[species]
    clarity_preference = profile["clarity"]

    rain_24h = weather_data.get("rain_24h", 0) or 0
    rain_72h = weather_data.get("rain_72h", 0) or 0
    river_change = 0

    if river_data:
        river_change = river_data.get("change_cm", 0) or 0

    positives = []
    negatives = []
    neutrals = []
    score = 6.5

    if clarity_preference == "clear":
        if rain_72h < 5 and abs(river_change) < 10:
            score = 8.5
            positives.append("Recent rain is low, so water is more likely to be clear.")
        else:
            score = 4.5
            negatives.append("Recent rain or river movement may reduce clarity, which is poor for this species.")

    elif clarity_preference == "slightly_coloured":
        if 2 <= rain_72h <= 20:
            score = 8.5
            positives.append("Recent rain should add useful colour without making it too dirty.")
        elif rain_72h > 30:
            score = 4.5
            negatives.append("Heavy recent rain may make the water too coloured.")
        else:
            score = 6.5
            neutrals.append("Water clarity is likely neutral.")

    elif clarity_preference == "clear_to_slight_colour":
        if rain_72h <= 15 and river_change <= 20:
            score = 8
            positives.append("Water is likely clear to slightly coloured, which suits this species.")
        elif rain_72h > 25 or river_change > 30:
            score = 4.5
            negatives.append("Water may be too coloured or unsettled.")
        else:
            score = 6.5
            neutrals.append("Water clarity looks workable but not perfect.")

    elif clarity_preference == "falling_and_clearing":
        if -20 <= river_change <= 0 and rain_24h < 8:
            score = 9
            positives.append("River appears to be falling/clearing, which is ideal.")
        elif 0 < river_change <= 25:
            score = 7.5
            positives.append("River has some lift, which can encourage movement.")
        elif river_change > 35 or rain_72h > 30:
            score = 4
            negatives.append("River may be too high or dirty.")
        else:
            score = 6
            neutrals.append("River clarity/trend is not clearly ideal.")

    return make_component(
        "Water clarity",
        score,
        f"Water clarity preference: {clarity_preference.replace('_', ' ')}.",
        positives=positives,
        negatives=negatives,
        neutrals=neutrals,
    )


def score_location_species(location, species):
    if location == "Wansbeck Estuary":
        if species in ["Bass", "Flounder", "Sea Trout"]:
            return make_component(
                "Location",
                7,
                f"{location} is a realistic venue for {species}.",
                positives=[f"{species} are realistic at this mark."],
            )
        if species == "Mullet":
            return make_component(
                "Location",
                6,
                "Mullet are possible but very condition-specific.",
                neutrals=["Mullet need clearer, calmer and warmer conditions than most species here."],
            )

    if "Coquet" in location:
        if species == "Sea Trout":
            return make_component("Location", 8, "The Coquet is a strong sea trout option.", positives=["Good species/venue match."])
        if species == "Salmon":
            return make_component("Location", 7, "The Coquet can produce salmon, especially with water on.", positives=["Good option when river levels are right."])
        if species == "Brown Trout":
            return make_component("Location", 7, "The Coquet is a decent brown trout river.", positives=["Good general trout venue."])

    if location == "Wansbeck - Whorral Bank" and species == "Brown Trout":
        return make_component("Location", 8, "Whorral Bank is a strong brown trout option.", positives=["Strong location/species match."])

    if location in ["Langley Dam", "Chatton Trout Fishery", "Thrunton Long Crag"]:
        if species == "Rainbow Trout":
            return make_component("Location", 8, f"{location} is a suitable stocked rainbow trout venue.", positives=["Stocked trout venue."])

    if location in ["QE2 Park Lake", "Loch Ken", "Loch Rutton"]:
        if species in ["Pike", "Perch", "Roach", "Bream", "Carp", "Tench"]:
            return make_component("Location", 8, f"{location} is a suitable coarse fishing venue for {species}.", positives=["Good stillwater/species match."])

    return make_component("Location", 5, "Location/species suitability is neutral.", neutrals=["No strong venue rule has been added yet."])


def score_water(location, location_info, selected_date, selected_time):
    river_data = None
    tide_data = None

    if location_info["type"] == "river":
        river_data = get_river_data(location_info["lat"], location_info["lon"])
        score = river_data.get("river_score", 6.5)

        return make_component(
            "River/tide",
            score,
            f"River score is {score}/10.",
            positives=[] if score < 7.5 else ["River level trend looks useful."],
            negatives=[] if score >= 6 else ["River level trend looks poor."],
            neutrals=river_data.get("reasons", []),
        ), river_data, tide_data

    if location_info["type"] == "estuary":
        tide_data = get_tide_data(location, selected_time, selected_date)
        score = tide_data.get("tide_score", 6.5)

        return make_component(
            "River/tide",
            score,
            f"Tide score is {score}/10.",
            positives=[] if score < 7.5 else ["Tide timing looks favourable."],
            negatives=[] if score >= 5.5 else ["Tide timing looks weak."],
            neutrals=tide_data.get("reasons", []),
        ), river_data, tide_data

    return make_component(
        "River/tide",
        6.5,
        "Stillwater venue, so river/tide scoring is neutral for now.",
        neutrals=["Stillwater venue: river/tide scoring is not currently used."],
    ), river_data, tide_data


def get_confidence(weather_data, river_data, tide_data, location_type):
    missing = 0

    for key in ["temperature", "rain", "cloud", "wind", "wind_direction", "pressure", "rain_24h", "rain_72h"]:
        if weather_data.get(key) is None:
            missing += 1

    if location_type == "river" and not river_data:
        missing += 2

    if location_type == "estuary":
        if not tide_data:
            missing += 2
        elif tide_data.get("confidence") == "Low":
            missing += 2

    if missing <= 1:
        return "High"
    if missing <= 3:
        return "Medium"
    return "Low"


def build_summary(final_score, species, location, components):
    positives = []
    negatives = []

    for component in components.values():
        positives.extend(component["positives"])
        negatives.extend(component["negatives"])

    if final_score >= 8:
        verdict = f"Excellent option for {species} at {location}."
    elif final_score >= 6.5:
        verdict = f"Decent option for {species} at {location}."
    elif final_score >= 5:
        verdict = f"Fishable, but not a standout option for {species} at {location}."
    else:
        verdict = f"Poorer option for {species} at {location}."

    return {
        "verdict": verdict,
        "top_positives": positives[:3],
        "top_negatives": negatives[:3],
    }


def calculate_score(location, species, selected_date, selected_time, location_info):
    weather_data = get_weather(
        location_info["lat"],
        location_info["lon"],
        selected_date,
        selected_time,
    )

    season = score_season(species, selected_date)
    timing = score_time(species, selected_time)
    suitability = score_location_species(location, species)
    weather = score_weather_for_species(species, weather_data)
    pressure = score_pressure(species, weather_data)
    water, river_data, tide_data = score_water(location, location_info, selected_date, selected_time)
    clarity = score_clarity(location_info["type"], species, weather_data, river_data)

    components = {
        "season": season,
        "time": timing,
        "location": suitability,
        "weather": weather,
        "pressure": pressure,
        "water": water,
        "clarity": clarity,
    }

    final = 0
    for key, component in components.items():
        final += component["score"] * WEIGHTS[key]

    final = round(final, 1)

    old_style_reasons = []
    for component in components.values():
        old_style_reasons.append(component["explanation"])
        old_style_reasons.extend(component["positives"])
        old_style_reasons.extend(component["negatives"])
        old_style_reasons.extend(component["neutrals"])

    return {
        "score": final,
        "reasons": old_style_reasons,
        "components": components,
        "summary": build_summary(final, species, location, components),
        "confidence": get_confidence(weather_data, river_data, tide_data, location_info["type"]),
        "weather_data": weather_data,
        "river_data": river_data,
        "tide_data": tide_data,
    }