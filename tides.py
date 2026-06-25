import os
from datetime import datetime, date, time

import pandas as pd


TIDE_DATA_FILE = "tide_data.csv"

TIDE_COLUMNS = ["date", "location", "tide_type", "time"]


def load_tide_table():
    if not os.path.exists(TIDE_DATA_FILE):
        return pd.DataFrame(columns=TIDE_COLUMNS)

    return pd.read_csv(TIDE_DATA_FILE)


def save_tide_day(selected_date, location_name, low_times, high_times):
    df = load_tide_table()

    selected_date_str = str(selected_date)

    df = df[
        ~(
            (df["date"] == selected_date_str)
            & (df["location"] == location_name)
        )
    ]

    new_rows = []

    for low_time in low_times:
        low_time = low_time.strip()
        if low_time:
            new_rows.append(
                {
                    "date": selected_date_str,
                    "location": location_name,
                    "tide_type": "low",
                    "time": low_time,
                }
            )

    for high_time in high_times:
        high_time = high_time.strip()
        if high_time:
            new_rows.append(
                {
                    "date": selected_date_str,
                    "location": location_name,
                    "tide_type": "high",
                    "time": high_time,
                }
            )

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    df.to_csv(TIDE_DATA_FILE, index=False)


def get_saved_tide_events(location_name, selected_date):
    df = load_tide_table()

    if df.empty:
        return []

    selected_date_str = str(selected_date)

    rows = df[
        (df["date"] == selected_date_str)
        & (df["location"] == location_name)
    ]

    events = []

    for _, row in rows.iterrows():
        try:
            hour, minute = str(row["time"]).split(":")
            tide_datetime = datetime.combine(selected_date, time(int(hour), int(minute)))

            events.append(
                {
                    "type": row["tide_type"],
                    "datetime": tide_datetime,
                }
            )
        except Exception:
            continue

    return sorted(events, key=lambda x: x["datetime"])


def minutes_between(a, b):
    return abs((a - b).total_seconds()) / 60


def describe_minutes(minutes):
    minutes = int(round(minutes))

    if minutes < 60:
        return f"{minutes} minutes"

    hours = minutes // 60
    mins = minutes % 60

    if mins == 0:
        return f"{hours}h"

    return f"{hours}h {mins}m"


def score_low_water(minutes_from_low):
    if minutes_from_low <= 45:
        return 1.5, "low water / very little fishable water", [
            "Selected time is very close to low water.",
            "The estuary may have very little fishable water.",
            "This should heavily reduce bass, flounder, sea trout and mullet scores here.",
        ]

    if minutes_from_low <= 90:
        return 2.5, "near low water", [
            "Selected time is within 90 minutes of low water.",
            "This is usually a weak estuary window.",
            "Waiting for the flood to push in would usually be better.",
        ]

    if minutes_from_low <= 150:
        return 5.0, "early flood / recovering after low", [
            "The tide should be starting to recover after low water.",
            "Fishing may improve later as more water and bait push in.",
        ]

    if minutes_from_low <= 270:
        return 7.5, "flood tide", [
            "The tide should be flooding with useful water movement.",
            "Moving water can push bait and scent through the estuary.",
        ]

    return 6.5, "away from low water", [
        "Selected time is not close to low water.",
        "Without complete high/low context, this is scored cautiously.",
    ]


def score_high_water(minutes_from_high):
    if minutes_from_high <= 30:
        return 5.5, "slack high water", [
            "Selected time is very close to high water.",
            "Slack water can reduce feeding activity.",
        ]

    if minutes_from_high <= 120:
        return 7.0, "early ebb", [
            "Selected time is after high water on the early ebb.",
            "Food and bait can be pulled back through channels.",
        ]

    return 6.5, "away from high water", [
        "Selected time is not close to high water.",
        "This can be fishable if there is still enough movement and depth.",
    ]


def get_tide_data(location_name, selected_time, selected_date=None):
    if location_name != "Wansbeck Estuary":
        return {
            "tide_score": 6.5,
            "tide_phase": "not tidal",
            "reasons": ["This location does not need tide scoring."],
            "confidence": "High",
        }

    if selected_date is None:
        selected_date = date.today()

    selected_datetime = datetime.combine(selected_date, selected_time)
    tide_events = get_saved_tide_events(location_name, selected_date)

    if not tide_events:
        return {
            "tide_score": 3.5,
            "tide_phase": "unknown tide",
            "reasons": [
                f"No tide times saved for {location_name} on {selected_date}.",
                "The app is scoring this cautiously instead of guessing.",
                "Add high/low tide times in the Tide data tab.",
            ],
            "confidence": "Low",
        }

    nearest_event = min(
        tide_events,
        key=lambda event: minutes_between(selected_datetime, event["datetime"]),
    )

    nearest_minutes = minutes_between(selected_datetime, nearest_event["datetime"])

    if nearest_event["type"] == "low":
        score, phase, extra = score_low_water(nearest_minutes)
    else:
        score, phase, extra = score_high_water(nearest_minutes)

    event_summary = [
        f"{event['type'].title()} water at {event['datetime'].strftime('%H:%M')}"
        for event in tide_events
    ]

    return {
        "tide_score": score,
        "tide_phase": phase,
        "nearest_tide_type": nearest_event["type"],
        "nearest_tide_time": nearest_event["datetime"].strftime("%H:%M"),
        "minutes_from_nearest_tide": round(nearest_minutes),
        "events": event_summary,
        "reasons": [
            f"Saved tide data used for {location_name} on {selected_date}.",
            f"Nearest tide event: {nearest_event['type']} water at {nearest_event['datetime'].strftime('%H:%M')}.",
            f"Selected time is {describe_minutes(nearest_minutes)} from {nearest_event['type']} water.",
            f"Estimated tide stage: {phase}.",
            f"Tide score calculated as {score}/10.",
            *event_summary,
            *extra,
        ],
        "confidence": "Medium",
    }