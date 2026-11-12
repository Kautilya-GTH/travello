"""Travello — AI trip planner (MVP).

Workflow: trip brief form -> Gemini itinerary -> day cards.
(Chat edits and download come in later build steps.)
"""
import json
from pathlib import Path

import streamlit as st

import planner

DATA_PATH = Path(__file__).parent / "data" / "places.json"
DEFAULT_MODEL = "gemini-3.8-flash"

INTERESTS = ["Sightseeing", "Culture", "Nature", "Adventure", "Relaxation", "Shopping"]
FOOD_PREFS = ["Local food", "Street food", "Cafés", "Vegetarian", "Fine dining"]
COMPANIONS = ["Solo", "Partner", "Friends", "Family with kids", "Family (adults)"]

st.set_page_config(page_title="Travello", page_icon="🧭", layout="centered")


@st.cache_data
def load_places():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["destinations"]


@st.cache_resource
def get_client(api_key):
    from google import genai

    return genai.Client(api_key=api_key)


def get_settings():
    """Read the key and model from Streamlit secrets (never shown or logged)."""
    try:
        return st.secrets.get("GEMINI_API_KEY"), st.secrets.get("GEMINI_MODEL", DEFAULT_MODEL)
    except Exception:  # no secrets.toml at all
        return None, DEFAULT_MODEL


def lookup(dest):
    """id -> place dict, across every category of one destination."""
    return {p["id"]: p for cat in ("sights", "food", "stays", "extras") for p in dest[cat]}


def show_itinerary(itin, dest):
    places = lookup(dest)
    if itin["summary"]:
        st.write(itin["summary"])

    for day in itin["days"]:
        with st.container(border=True):
            st.markdown(f"### Day {day['day']}" + (f" · {day['title']}" if day["title"] else ""))
            for slot in planner.SLOTS:
                st.markdown(f"**{slot.capitalize()}**")
                if not day[slot]:
                    st.markdown("- _Free time_")
                for item in day[slot]:
                    p = places[item["id"]]
                    extra = p.get("dur") or p.get("price") or ""
                    line = f"- **{p['name']}**" + (f" ({extra})" if extra else "")
                    line += f" — {item['note'] or p['note']}"
                    st.markdown(line)

    stay = itin["stay"]
    with st.container(border=True):
        st.markdown("### 🏨 Recommended stay")
        if stay:
            s = places[stay["id"]]
            st.markdown(
                f"**{s['name']}** · {s['type']} · ₹{s['price']:,}/night · ⭐ {s['rating']}"
            )
            st.write(stay["note"] or s["note"])
        else:
            st.write("No stay could be matched this time — try generating again.")
        st.caption("Stays are sample listings, not verified properties or bookings.")


# ---------------- Page ----------------
destinations = load_places()
api_key, model = get_settings()

st.title("🧭 Travello")
st.caption("Tell us about your trip and get a day-by-day plan built from curated places.")

if not api_key:
    st.error("No GEMINI_API_KEY found in secrets. Add it to run the planner.")
    st.stop()

# --- 1. Trip brief form ---
with st.form("trip_form"):
    dest_key = st.selectbox(
        "Destination",
        options=list(destinations),
        format_func=lambda k: f"{destinations[k]['name']}, {destinations[k]['country']}",
    )
    col1, col2 = st.columns(2)
    days = col1.slider("Number of days", 2, 10, 3)
    budget = col2.radio("Budget", list(planner.BUDGET_TIER), index=1, horizontal=True)
    companions = col1.selectbox("Travelling with", COMPANIONS)
    pace = col2.radio("Pace", list(planner.PACE_ITEMS), index=1, horizontal=True)
    interests = st.multiselect("Interests", INTERESTS)
    food = st.multiselect("Food preferences", FOOD_PREFS)
    submitted = st.form_submit_button("Generate itinerary", type="primary")

# --- 2. Generate itinerary ---
if submitted:
    brief = {
        "days": days,
        "budget": budget,
        "companions": companions,
        "pace": pace,
        "interests": interests,
        "food": food,
    }
    with st.spinner("Planning your trip…"):
        try:
            itin, warnings = planner.generate_itinerary(
                get_client(api_key), model, brief, destinations[dest_key]
            )
        except planner.PlannerError as e:
            st.error(str(e))
        else:
            # Kept in session_state so later edits build on the latest version.
            st.session_state.itinerary = itin
            st.session_state.dest_key = dest_key
            st.session_state.brief = brief
            st.session_state.warnings = warnings

if "itinerary" in st.session_state:
    dest = destinations[st.session_state.dest_key]
    st.header(f"Your {st.session_state.brief['days']}-day {dest['name']} trip")
    for w in st.session_state.warnings:
        st.warning(w)
    show_itinerary(st.session_state.itinerary, dest)

# --- Temporary: connection check from Step 1 (removed in Step 4) ---
with st.expander("Developer: test Gemini connection"):
    if st.button("Test Gemini"):
        try:
            resp = get_client(api_key).models.generate_content(
                model=model, contents="Reply with exactly: Travello connected."
            )
            st.success(f"{model}: {resp.text.strip()}")
        except Exception as e:  # show the real error so we can debug it
            st.error(f"Gemini call failed: {e}")
