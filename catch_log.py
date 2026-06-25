import os
import pandas as pd


CATCH_LOG_FILE = "catch_log.csv"


COLUMNS = [
    "date",
    "time",
    "location",
    "species",
    "method",
    "length_cm",
    "weight_lb",
    "notes",
]


def load_catches():
    if not os.path.exists(CATCH_LOG_FILE):
        return pd.DataFrame(columns=COLUMNS)

    return pd.read_csv(CATCH_LOG_FILE)


def save_catch(catch_data):
    df = load_catches()
    new_row = pd.DataFrame([catch_data])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(CATCH_LOG_FILE, index=False)


def get_catch_stats():
    df = load_catches()

    if df.empty:
        return {
            "total_catches": 0,
            "best_species": None,
            "best_location": None,
            "df": df,
        }

    best_species = df["species"].value_counts().idxmax()
    best_location = df["location"].value_counts().idxmax()

    return {
        "total_catches": len(df),
        "best_species": best_species,
        "best_location": best_location,
        "df": df,
    }   