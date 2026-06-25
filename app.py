import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time

import pandas as pd
import streamlit as st

from locations import LOCATIONS
from methods import get_method, get_method_details
from scoring import WEIGHTS, calculate_score
from scoring_v2 import calculate_score_v2
from tides import save_tide_day, load_tide_table


CATCH_LOG_FILE = "catch_log.csv"


st.set_page_config(page_title="Fishing Predictor", page_icon="🎣", layout="wide")


st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(180deg, #f8fbfb 0%, #eef7f4 100%); }
    h1, h2, h3 { color: #123c3a; }

    .hero-card, .info-card, .best-card, .method-card, .v2-card {
        background: white;
        border: 1px solid #d8e9e4;
        border-radius: 20px;
        padding: 18px;
        margin: 12px 0;
        box-shadow: 0 4px 14px rgba(18, 60, 58, 0.06);
    }

    .hero-card {
        background: linear-gradient(135deg, #ffffff 0%, #e8f7f3 100%);
        border-radius: 24px;
        padding: 24px;
    }

    .best-card { border-left: 8px solid #2e8b7d; }
    .method-card { border-left: 6px solid #2e8b7d; }
    .v2-card { border-left: 6px solid #3b82f6; }

    .badge {
        display: inline-block;
        border-radius: 999px;
        padding: 5px 11px;
        font-weight: 700;
        font-size: 0.82rem;
        margin-right: 6px;
    }

    .badge-good { background: #dff7eb; color: #11633f; }
    .badge-mid { background: #fff4cc; color: #7a5a00; }
    .badge-bad { background: #ffe1df; color: #8f1f17; }
    .mini-muted { color: #607875; font-size: 0.95rem; }

    [data-testid="stMetric"] {
        background: white;
        border: 1px solid #d8e9e4;
        padding: 16px;
        border-radius: 18px;
        box-shadow: 0 4px 12px rgba(18, 60, 58, 0.06);
    }

    div[data-testid="stExpander"] {
        background: white;
        border-radius: 16px;
        border: 1px solid #d8e9e4;
    }

    .stButton > button {
        border-radius: 999px;
        padding: 0.6rem 1.2rem;
        font-weight: 700;
    }

    code {
        white-space: pre-wrap !important;
        border-radius: 12px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div class="hero-card">
        <h1>🎣 Fishing Conditions Predictor</h1>
        <p>Ranks venues, species and fishing windows using the V2 scoring model.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=900, show_spinner=False)
def cached_calculate_score(location_name, species, selected_date, selected_time, location_info):
    return calculate_score(location_name, species, selected_date, selected_time, location_info)


def get_all_species():
    return sorted({species for info in LOCATIONS.values() for species in info["species"]})


def score_colour(score):
    if score >= 8:
        return "🟢"
    if score >= 6:
        return "🟡"
    return "🔴"


def score_badge(score):
    if score >= 8:
        return '<span class="badge badge-good">Excellent</span>'
    if score >= 6.5:
        return '<span class="badge badge-good">Good</span>'
    if score >= 5:
        return '<span class="badge badge-mid">Fair</span>'
    return '<span class="badge badge-bad">Poor</span>'


def rating(score):
    if score >= 8:
        return "Excellent"
    if score >= 6.5:
        return "Good"
    if score >= 5:
        return "Fair"
    return "Poor"


def load_catches():
    columns = ["date", "time", "location", "species", "method", "length_cm", "weight_lb", "notes"]

    if not os.path.exists(CATCH_LOG_FILE):
        return pd.DataFrame(columns=columns)

    return pd.read_csv(CATCH_LOG_FILE)


def save_catch(catch_data):
    df = load_catches()
    df = pd.concat([df, pd.DataFrame([catch_data])], ignore_index=True)
    df.to_csv(CATCH_LOG_FILE, index=False)


def run_all_locations(selected_date, selected_time, selected_species):
    tasks = []

    for location_name, location_info in LOCATIONS.items():
        for species in location_info["species"]:
            if selected_species and species not in selected_species:
                continue

            tasks.append((location_name, species, selected_date, selected_time, location_info))

    if not tasks:
        return []

    results = []
    progress = st.progress(0)
    status = st.empty()

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_task = {
            executor.submit(
                cached_calculate_score,
                location_name,
                species,
                selected_date,
                selected_time,
                location_info,
            ): (
                location_name,
                species,
                selected_date,
                selected_time,
                location_info,
            )
            for location_name, species, selected_date, selected_time, location_info in tasks
        }

        completed = 0

        for future in as_completed(future_to_task):
            location_name, species, selected_date, selected_time, location_info = future_to_task[future]
            completed += 1
            status.write(f"Checked {completed}/{len(tasks)} options...")

            try:
                old_score_data = future.result()
                v2_data = calculate_score_v2(
                    location_name,
                    species,
                    selected_date,
                    selected_time,
                    location_info,
                    old_score_data,
                )

                results.append(
                    {
                        "location": location_name,
                        "species": species,
                        "time": selected_time.strftime("%H:%M"),
                        "score": v2_data["score"],
                        "old_score": old_score_data["score"],
                        "v2_data": v2_data,
                        "summary": old_score_data["summary"],
                        "confidence": old_score_data["confidence"],
                        "components": old_score_data["components"],
                        "weather_data": old_score_data["weather_data"],
                        "river_data": old_score_data["river_data"],
                        "tide_data": old_score_data["tide_data"],
                        "method": get_method(species),
                    }
                )

            except Exception as e:
                results.append(
                    {
                        "location": location_name,
                        "species": species,
                        "time": selected_time.strftime("%H:%M"),
                        "score": 0,
                        "old_score": 0,
                        "v2_data": None,
                        "summary": {
                            "verdict": f"Could not calculate this option: {e}",
                            "top_positives": [],
                            "top_negatives": [str(e)],
                        },
                        "confidence": "Low",
                        "components": {},
                        "weather_data": {},
                        "river_data": None,
                        "tide_data": None,
                        "method": get_method(species),
                    }
                )

            progress.progress(completed / len(tasks))

    status.empty()
    progress.empty()

    return sorted(results, key=lambda x: x["score"], reverse=True)


def show_best_pick(results):
    if not results:
        st.warning("No results found for your selected filters.")
        return

    best = results[0]

    st.subheader("Best pick")

    col1, col2, col3 = st.columns(3)
    col1.metric("Score", f"{best['score']} / 10")
    col2.metric("Species", best["species"])
    col3.metric("Location", best["location"])

    st.markdown(
        f"""
        <div class="best-card">
            <h3>{score_colour(best["score"])} {best["location"]} — {best["species"]}</h3>
            <p>{score_badge(best["score"])} <strong>{best["score"]}/10</strong></p>
            <p>{best["summary"]["verdict"]}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_method_details(species):
    profile = get_method_details(species)

    st.markdown(
        f"""
        <div class="method-card">
            <h3>🎣 Recommended method: {species}</h3>
            <p>{profile["headline"]}</p>
            <p><strong>Best for:</strong> {profile["best_for"]}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not profile["setups"]:
        st.info("No detailed rig profile has been added for this species yet.")
        return

    for setup in profile["setups"]:
        with st.expander(f"Rig / method: {setup['title']}", expanded=True):
            st.write("### Rig diagram")
            st.code(setup["diagram"])

            col1, col2 = st.columns(2)

            with col1:
                st.write("### Tackle")
                for item in setup["tackle"]:
                    st.write(f"• {item}")

            with col2:
                st.write("### Tips")
                for tip in setup["tips"]:
                    st.write(f"✅ {tip}")

            st.write("### How to set it up")
            for i, step in enumerate(setup["steps"], start=1):
                st.write(f"**{i}.** {step}")


def show_v2_breakdown(result):
    v2_data = result.get("v2_data")

    if not v2_data:
        return

    st.markdown(
        f"""
        <div class="v2-card">
            <h3>🧪 Scoring model</h3>
            <p><strong>Model:</strong> {v2_data["model_version"]}</p>
            <p><strong>Main score:</strong> {result["score"]}/10</p>
            <p>{v2_data["summary"]["comparison"]}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rows = []

    for factor_name, factor_data in v2_data["factors"].items():
        rows.append(
            {
                "Factor": factor_name.replace("_", " ").title(),
                "Score": factor_data["score"],
                "Weight": f"{round(v2_data['weights'].get(factor_name, 0) * 100)}%",
                "Confidence": factor_data["confidence"],
                "Reason": factor_data["reason"],
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Why it scored this way"):
        st.write("### Strongest factors")
        for item in v2_data["summary"]["strongest"]:
            st.write(f"✅ {item}")

        st.write("### Weakest factors")
        for item in v2_data["summary"]["weakest"]:
            st.write(f"⚠️ {item}")


def show_result_full_breakdown(result):
    col1, col2, col3 = st.columns(3)
    col1.metric("Score", f"{result['score']} / 10")
    col2.metric("Species", result["species"])
    col3.metric("Confidence", result["confidence"])

    st.write(result["summary"]["verdict"])

    show_v2_breakdown(result)

    st.divider()
    show_method_details(result["species"])

    with st.expander("Diagnostics / old model / raw data"):
        st.write(f"Old score: {result['old_score']} / 10")

        if result["components"]:
            st.write("### Old scoring breakdown")
            breakdown_rows = []
            for key, component in result["components"].items():
                breakdown_rows.append(
                    {
                        "Component": component["name"],
                        "Score": component["score"],
                        "Weight": f"{int(WEIGHTS[key] * 100)}%",
                        "Explanation": component["explanation"],
                    }
                )
            st.dataframe(breakdown_rows, use_container_width=True, hide_index=True)

        st.write("### Weather")
        st.json(result["weather_data"])

        if result["river_data"]:
            st.write("### River")
            st.json(result["river_data"])

        if result["tide_data"]:
            st.write("### Tide")
            st.json(result["tide_data"])


def show_ranked_options(results):
    st.subheader("Ranked options")

    for i, result in enumerate(results, start=1):
        title = (
            f"#{i} {score_colour(result['score'])} "
            f"{result['location']} — {result['species']} — "
            f"{result['time']} — {result['score']}/10"
        )

        with st.expander(title, expanded=(i == 1)):
            st.markdown(score_badge(result["score"]), unsafe_allow_html=True)
            show_result_full_breakdown(result)


def show_detailed_breakdown(results, key_prefix):
    if not results:
        return

    st.subheader("Compare / inspect any option")

    option_labels = [
        f"{r['location']} — {r['species']} — {r['time']} — {r['score']}/10"
        for r in results
    ]

    selected_option = st.selectbox("Choose an option", option_labels, key=f"{key_prefix}_breakdown")
    selected_result = results[option_labels.index(selected_option)]

    show_result_full_breakdown(selected_result)


def species_filter_widget(key_prefix):
    all_species = get_all_species()

    quick_group = st.radio(
        "Quick species group",
        ["All", "Predators", "Coarse", "Trout / Salmon", "Custom"],
        horizontal=True,
        key=f"{key_prefix}_quick_group",
    )

    if quick_group == "All":
        default_species = all_species
    elif quick_group == "Predators":
        default_species = [s for s in ["Bass", "Pike", "Perch", "Sea Trout"] if s in all_species]
    elif quick_group == "Coarse":
        default_species = [s for s in ["Pike", "Perch", "Roach", "Bream", "Carp", "Tench"] if s in all_species]
    elif quick_group == "Trout / Salmon":
        default_species = [s for s in ["Brown Trout", "Rainbow Trout", "Sea Trout", "Salmon"] if s in all_species]
    else:
        default_species = []

    selected_species = st.multiselect(
        "Target species",
        all_species,
        default=default_species,
        key=f"{key_prefix}_species_filter",
    )

    if not selected_species:
        st.warning("Select at least one species to check.")

    return selected_species


def best_at_chosen_time_tab():
    st.markdown(
        """
        <div class="info-card">
            <h3>Best at chosen time</h3>
            <p class="mini-muted">Ranks saved locations for one exact date and time, filtered by target species.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected_date = st.date_input("Date", datetime.now().date(), key="single_date")
    selected_time = st.time_input("Time", time(19, 0), key="single_time")

    selected_species = species_filter_widget("single")

    run_button = st.button("Check matching options", type="primary", key="single_run")

    if not run_button:
        st.info("Choose a date/time and target species, then click **Check matching options**.")
        return

    if not selected_species:
        st.stop()

    with st.spinner("Checking fishing conditions..."):
        results = run_all_locations(selected_date, selected_time, selected_species)

    st.divider()
    show_best_pick(results)

    st.divider()
    show_ranked_options(results)

    st.divider()
    show_detailed_breakdown(results, "single")


def hourly_forecast_tab():
    st.markdown(
        """
        <div class="info-card">
            <h3>Hourly forecast</h3>
            <p class="mini-muted">Checks every hour in your chosen range and ranks the best windows for your target species.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected_date = st.date_input("Date", datetime.now().date(), key="hourly_date")
    start_hour = st.slider("Start hour", 0, 23, 4, key="hourly_start")
    end_hour = st.slider("End hour", 1, 24, 23, key="hourly_end")
    max_results = st.slider("Show top results", 5, 50, 20, key="hourly_max")

    selected_species = species_filter_widget("hourly")

    if end_hour <= start_hour:
        st.warning("End hour must be later than start hour.")
        return

    run_button = st.button("Run hourly forecast", type="primary", key="hourly_run")

    if not run_button:
        st.info("Choose your hour range and target species, then click **Run hourly forecast**.")
        return

    if not selected_species:
        st.stop()

    all_results = []

    with st.spinner("Checking hourly fishing windows..."):
        for hour in range(start_hour, end_hour):
            selected_time = time(hour, 0)
            hourly_results = run_all_locations(selected_date, selected_time, selected_species)
            all_results.extend(hourly_results)

    all_results = sorted(all_results, key=lambda x: x["score"], reverse=True)
    top_results = all_results[:max_results]

    st.divider()
    st.subheader("Best fishing windows")

    rows = []
    for result in top_results:
        rows.append(
            {
                "Time": result["time"],
                "Location": result["location"],
                "Species": result["species"],
                "Score": result["score"],
                "Rating": rating(result["score"]),
                "Confidence": result["confidence"],
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.divider()
    show_best_pick(top_results)

    st.divider()
    show_ranked_options(top_results)

    st.divider()
    show_detailed_breakdown(top_results, "hourly")


def catch_log_tab():
    st.markdown(
        """
        <div class="info-card">
            <h3>Catch log</h3>
            <p class="mini-muted">Log your catches so the app can eventually learn your best conditions.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    all_species = get_all_species()

    with st.form("catch_form"):
        col1, col2 = st.columns(2)

        with col1:
            catch_date = st.date_input("Catch date", datetime.now().date(), key="catch_date")
            catch_time = st.time_input(
                "Catch time",
                datetime.now().time().replace(second=0, microsecond=0),
                key="catch_time",
            )
            location = st.selectbox("Location", list(LOCATIONS.keys()), key="catch_location")
            species = st.selectbox("Species", all_species, key="catch_species")

        with col2:
            method = st.text_input("Method / lure / bait", placeholder="e.g. Toby spinner, soft plastic, fly")
            length_cm = st.number_input("Length (cm)", min_value=0.0, step=1.0)
            weight_lb = st.number_input("Weight (lb)", min_value=0.0, step=0.1)
            notes = st.text_area("Notes", placeholder="Exact mark, tide stage, conditions, what happened...")

        submitted = st.form_submit_button("Save catch", type="primary")

        if submitted:
            save_catch(
                {
                    "date": str(catch_date),
                    "time": catch_time.strftime("%H:%M"),
                    "location": location,
                    "species": species,
                    "method": method,
                    "length_cm": length_cm,
                    "weight_lb": weight_lb,
                    "notes": notes,
                }
            )

            st.success("Catch saved.")

    st.divider()

    df = load_catches()

    st.subheader("Your catch stats")

    if df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total catches", 0)
        c2.metric("Top species", "None yet")
        c3.metric("Top location", "None yet")
        st.info("No catches logged yet.")
        return

    top_species = df["species"].value_counts().idxmax()
    top_location = df["location"].value_counts().idxmax()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total catches", len(df))
    c2.metric("Top species", top_species)
    c3.metric("Top location", top_location)

    st.dataframe(df, use_container_width=True, hide_index=True)


def tide_data_tab():
    st.markdown(
        """
        <div class="info-card">
            <h3>Tide data</h3>
            <p class="mini-muted">Enter real high and low tide times so estuary predictions do not rely on guesses.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected_date = st.date_input("Tide date", datetime.now().date(), key="tide_date")
    location_name = st.selectbox("Tidal location", ["Wansbeck Estuary"], key="tide_location")

    st.write("Enter times in 24-hour format, separated by commas.")

    low_times_text = st.text_input("Low tides", placeholder="e.g. 07:05, 19:18")
    high_times_text = st.text_input("High tides", placeholder="e.g. 00:55, 13:12")

    if st.button("Save tide times", type="primary", key="save_tides"):
        low_times = [x.strip() for x in low_times_text.split(",") if x.strip()]
        high_times = [x.strip() for x in high_times_text.split(",") if x.strip()]

        save_tide_day(selected_date, location_name, low_times, high_times)
        st.success("Tide times saved.")

    st.divider()
    st.subheader("Saved tide data")

    tide_df = load_tide_table()

    if tide_df.empty:
        st.info("No tide data saved yet.")
    else:
        st.dataframe(tide_df, use_container_width=True, hide_index=True)


tab1, tab2, tab3, tab4 = st.tabs(
    ["Best at chosen time", "Hourly forecast", "Catch log", "Tide data"]
)

with tab1:
    best_at_chosen_time_tab()

with tab2:
    hourly_forecast_tab()

with tab3:
    catch_log_tab()

with tab4:
    tide_data_tab()