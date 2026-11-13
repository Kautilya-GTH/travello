"""Travello — AI trip planner (MVP).

Workflow (one page, three views kept in st.session_state.view):
  home   -> hero + four destination cards
  wizard -> 3-step trip brief (destination & days, budget & company, travel style)
  plan   -> Gemini itinerary (summary card + day cards), edit by chat, download
"""
import base64
import json
from pathlib import Path

import streamlit as st

import planner

ROOT = Path(__file__).parent
DATA_PATH = ROOT / "data" / "places.json"
ASSETS = ROOT / "assets"
DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Card text for the home screen (same copy as the prototype).
TAGLINES = {
    "kyoto": "Culture & calm",
    "bali": "A slower escape",
    "goa": "Coast & colour",
    "jaipur": "Heritage & discovery",
}
CARD_ORDER = ["kyoto", "bali", "goa", "jaipur"]

COMPANIONS = ["Solo", "Couple", "Friends", "Family", "Group"]
INTERESTS = ["Sightseeing", "Nature", "Culture", "Shopping", "Adventure", "Relaxation"]
FOOD_PREFS = ["Vegetarian", "Local food", "Street food", "Cafés", "Fine dining"]
STAY_TYPES = ["No preference", "Hotel", "Boutique", "Airbnb"]
STEP_NAMES = ["Destination & dates", "Budget & company", "Travel preferences"]

st.set_page_config(page_title="Travello", page_icon=str(ASSETS / "pin.png"), layout="centered")


# ---------------- Data, client, settings ----------------
@st.cache_data
def load_places():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["destinations"]


@st.cache_resource
def get_client(api_key):
    from google import genai
    from google.genai import types

    # 30s timeout so a hung model fails fast (as a 504) and the planner can
    # move on to the fallback model instead of freezing the page.
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30_000))


def get_settings():
    """Read the key and model from Streamlit secrets (never shown or logged)."""
    try:
        return st.secrets.get("GEMINI_API_KEY"), st.secrets.get("GEMINI_MODEL", DEFAULT_MODEL)
    except Exception:  # no secrets.toml at all
        return None, DEFAULT_MODEL


@st.cache_data
def img_b64(name):
    """An image from assets/ as a data URI, for the HTML banner and cards."""
    return "data:image/jpeg;base64," + base64.b64encode((ASSETS / name).read_bytes()).decode()


def lookup(dest):
    """id -> place dict, across every category of one destination."""
    return {p["id"]: p for cat in ("sights", "food", "stays", "extras") for p in dest[cat]}


# ---------------- Navigation helpers (button callbacks) ----------------
def go(view, step=1):
    st.session_state.view = view
    st.session_state.step = step


def start_plan(dest_key=None):
    if dest_key:
        st.session_state.w_dest = dest_key
    go("wizard", 1)


# ---------------- Home ----------------
def photo_block(image, height, inner_html, radius=22):
    """Photo with a dark fade and white text on top (like the prototype cards)."""
    st.html(f"""
    <div style="position:relative; height:{height}px; border-radius:{radius}px; overflow:hidden;
                background:url('{img_b64(image)}') center / cover; font-family:'Inter',sans-serif;
                color:#fff;">
      <div style="position:absolute; inset:0;
                  background:linear-gradient(180deg, rgba(10,30,40,0) 35%, rgba(10,30,40,.75) 100%);"></div>
      <div style="position:absolute; left:20px; right:20px; bottom:18px;">{inner_html}</div>
    </div>
    """)


def show_home(destinations):
    photo_block("hero.jpg", 320, """
        <div style="font-size:12px; font-weight:700; letter-spacing:2px;">YOUR NEXT CHAPTER</div>
        <div style="font-size:40px; font-weight:800; line-height:1.08; margin:6px 0 8px;">
          Away from<br>the everyday.</div>
        <div style="font-size:16px; opacity:.92;">A good trip starts with a little inspiration.</div>
    """)
    st.button(
        "Plan my trip", type="primary", icon=":material/auto_awesome:", width="stretch",
        on_click=start_plan,
    )

    row = st.container(horizontal=True, vertical_alignment="bottom")
    row.subheader("Where will you go?")
    row.caption("Four places to begin")

    for pair in (CARD_ORDER[:2], CARD_ORDER[2:]):
        cols = st.columns(2)
        for col, key in zip(cols, pair):
            d = destinations[key]
            with col:
                photo_block(f"{key}.jpg", 200, f"""
                    <div style="font-size:24px; font-weight:800;">{d['name']}</div>
                    <div style="font-size:13px; opacity:.95;">{d['country']} · {TAGLINES[key]}</div>
                """, radius=18)
                st.button(
                    f"Plan {d['name']}", key=f"card_{key}", icon=":material/arrow_forward:",
                    width="stretch", on_click=start_plan, args=(key,),
                )

    st.caption(
        "Coming later: Community (share and discover routes), My trips and Profile."
    )


# ---------------- Wizard ----------------
def wizard_header(step):
    """Back arrow + title + 3-part progress bar, like the prototype's wizard header."""
    top = st.container(horizontal=True, vertical_alignment="center")
    # Back goes to the previous step, or home from step 1.
    back_args = ("home",) if step == 1 else ("wizard", step - 1)
    top.button("", icon=":material/arrow_back:", type="tertiary", key="wiz_back",
               on_click=go, args=back_args, help="Back")
    top.markdown(f"#### Plan a trip  \n:gray[Trip details · {step} of 3]")
    st.progress(step / 3, text=f"**Step {step} of 3** · {STEP_NAMES[step - 1]}")


def show_wizard(destinations, api_key, model):
    step = st.session_state.step
    wizard_header(step)

    if step == 1:
        st.header("Where are you heading?")
        st.caption("A few trip details first. Your planner will take it from there.")
        st.pills(
            "Which destination?", list(destinations), key="w_dest", persist_state="session",
            format_func=lambda k: destinations[k]["name"],
        )
        st.selectbox(
            "How long are you going?", list(range(2, 11)), key="w_days", persist_state="session",
            format_func=lambda n: f"{n} days",
        )
        st.caption("Destinations: Goa, Jaipur, Kyoto and Bali. Trips of 2–10 days.")
        back, nxt = st.columns([1, 2])
        back.button("Cancel", width="stretch", on_click=go, args=("home",))
        if nxt.button("Continue", type="primary", icon=":material/arrow_forward:", width="stretch"):
            if st.session_state.get("w_dest"):
                go("wizard", 2)
                st.rerun()
            st.warning("Pick a destination to continue.")

    elif step == 2:
        st.header("Who's coming along?")
        st.caption("Budget and company help shape your itinerary.")
        st.segmented_control(
            "What's your budget?", list(planner.BUDGET_TIER), key="w_budget",
            persist_state="session", required=True, width="stretch",
        )
        st.caption("Budget picks the stay: Budget = tier 1, Mid-range = tier 2, Premium = tier 3.")
        st.pills(
            "Who are you travelling with?", COMPANIONS, key="w_companions",
            persist_state="session", required=True,
        )
        back, nxt = st.columns([1, 2])
        back.button("Back", width="stretch", on_click=go, args=("wizard", 1))
        nxt.button(
            "Continue", type="primary", icon=":material/arrow_forward:", width="stretch",
            on_click=go, args=("wizard", 3),
        )

    else:
        st.header("What's your travel style?")
        st.caption("One last step — make the trip feel like you. Optional: pick what matters.")
        st.pills(
            "What would you like to explore?", INTERESTS, selection_mode="multi",
            key="w_interests", persist_state="session",
        )
        c1, c2 = st.columns(2)
        c1.selectbox(
            "Your pace", list(planner.PACE_ITEMS), key="w_pace", persist_state="session",
        )
        c2.selectbox(
            "Where would you like to stay?", STAY_TYPES, key="w_stay", persist_state="session",
        )
        st.pills(
            "Any food preferences?", FOOD_PREFS, selection_mode="multi", key="w_food",
            persist_state="session",
        )
        back, nxt = st.columns([1, 2])
        back.button("Back", width="stretch", on_click=go, args=("wizard", 2))
        if nxt.button(
            "Build my itinerary", type="primary", icon=":material/arrow_forward:", width="stretch"
        ):
            generate(destinations, api_key, model)


def generate(destinations, api_key, model):
    ss = st.session_state
    brief = {
        "days": ss.w_days,
        "budget": ss.w_budget,
        "companions": ss.w_companions,
        "pace": ss.w_pace,
        "stay_type": ss.w_stay,
        "interests": ss.w_interests or [],
        "food": ss.w_food or [],
    }
    with st.spinner("Planning your trip…"):
        try:
            itin, warnings = planner.generate_itinerary(
                get_client(api_key), model, brief, destinations[ss.w_dest]
            )
        except planner.PlannerError as e:
            st.error(str(e))
            return
    # Kept in session_state so later edits build on the latest version.
    ss.itinerary, ss.warnings, ss.brief, ss.dest_key = itin, warnings, brief, ss.w_dest
    ss.chat = [{"role": "assistant", "content": "Your itinerary is ready. Adjust it below, or download it when you're happy."}]
    go("plan")
    st.rerun()


# ---------------- Plan ----------------
def show_day_cards(itin, dest):
    places = lookup(dest)
    if itin["summary"]:
        st.write(itin["summary"])
    for day in itin["days"]:
        with st.container(border=True):
            st.markdown(f"**Day {day['day']}**" + (f" · {day['title']}" if day["title"] else ""))
            for slot in planner.SLOTS:
                st.markdown(f":gray[{slot.capitalize()}]")
                if not day[slot]:
                    st.markdown("- _Free time_")
                for item in day[slot]:
                    p = places[item["id"]]
                    extra = p.get("dur") or p.get("price") or ""
                    line = f"- **{p['name']}**" + (f" ({extra})" if extra else "")
                    line += f" — {item['note'] or p['note']}"
                    st.markdown(line)


def show_summary_card(itin, dest, brief):
    places = lookup(dest)
    stay = itin["stay"]
    stops = sum(len(day[slot]) for day in itin["days"] for slot in planner.SLOTS)
    with st.container(border=True):
        st.markdown(f"### {dest['name']} · {len(itin['days'])} days")
        stay_name = places[stay["id"]]["name"] if stay else "no stay matched"
        st.caption(f"{stops} stops · {stay_name}")
        if stay:
            s = places[stay["id"]]
            st.markdown(f"**{s['name']}** · {s['type']} · ₹{s['price']:,}/night · ⭐ {s['rating']}")
            st.caption((stay["note"] or s["note"]) + " · Sample stay, not a verified listing or booking.")
        food = ", ".join(brief["food"]) or "Any food"
        st.caption(f"{brief['pace']} pace · {brief['budget']} · {brief['companions']} · {food}")
        st.divider()
        for day in itin["days"]:
            names = [places[i["id"]]["name"] for slot in planner.SLOTS for i in day[slot]]
            st.markdown(f"**Day {day['day']}** &nbsp; " + (" · ".join(names) or "Free time"))


def itinerary_markdown(itin, dest, brief):
    """Same content as the day cards, as a Markdown file the user can keep."""
    places = lookup(dest)
    lines = [f"# Your {len(itin['days'])}-day {dest['name']} trip (Travello)", ""]
    lines.append(
        f"Budget: {brief['budget']} · Travelling with: {brief['companions']} · Pace: {brief['pace']}"
    )
    if itin["summary"]:
        lines += ["", itin["summary"]]

    for day in itin["days"]:
        lines += ["", f"## Day {day['day']}" + (f" · {day['title']}" if day["title"] else "")]
        for slot in planner.SLOTS:
            lines += ["", f"**{slot.capitalize()}**"]
            if not day[slot]:
                lines.append("- Free time")
            for item in day[slot]:
                p = places[item["id"]]
                extra = p.get("dur") or p.get("price") or ""
                lines.append(
                    f"- {p['name']}" + (f" ({extra})" if extra else "")
                    + f" — {item['note'] or p['note']}"
                )

    lines += ["", "## Recommended stay"]
    stay = itin["stay"]
    if stay:
        s = places[stay["id"]]
        lines.append(f"{s['name']} · {s['type']} · ₹{s['price']:,}/night · rating {s['rating']}")
        lines.append(stay["note"] or s["note"])
    else:
        lines.append("No stay could be matched.")
    lines += ["", "_Stays are sample listings, not verified properties or bookings._"]
    return "\n".join(lines)


def apply_edit(request, dest, api_key, model):
    """Send the current plan + the user's change to Gemini and keep the new version."""
    ss = st.session_state
    ss.chat.append({"role": "user", "content": request})
    with st.spinner("Updating your plan…"):
        try:
            itin, warnings, changes = planner.edit_itinerary(
                get_client(api_key), model, ss.brief, dest, ss.itinerary, request
            )
        except planner.PlannerError as e:
            ss.chat.append({"role": "assistant", "content": f"Sorry — {e} Your plan is unchanged."})
            return
    ss.itinerary, ss.warnings = itin, warnings
    ss.brief = {**ss.brief, "days": len(itin["days"])}
    ss.chat.append({"role": "assistant", "content": changes or "Done — your plan is updated."})


def show_plan(destinations, api_key, model):
    ss = st.session_state
    dest = destinations[ss.dest_key]

    # Pinned to the bottom of the page, like the prototype's chat bar.
    request = st.chat_input("Change days, budget or any activity…")
    if request:
        apply_edit(request, dest, api_key, model)

    top = st.container(horizontal=True, vertical_alignment="center")
    top.button("", icon=":material/arrow_back:", type="tertiary", key="plan_back",
               on_click=go, args=("home",), help="Back to home")
    top.markdown(f"#### {dest['name']} · your plan")

    for msg in ss.chat:
        with st.chat_message(msg["role"], avatar=str(ASSETS / "pin.png") if msg["role"] == "assistant" else None):
            st.write(msg["content"])

    for w in ss.warnings:
        st.warning(w)
    show_summary_card(ss.itinerary, dest, ss.brief)

    st.download_button(
        "Download itinerary",
        data=itinerary_markdown(ss.itinerary, dest, ss.brief),
        file_name=f"travello-{ss.dest_key}-{len(ss.itinerary['days'])}-days.md",
        mime="text/markdown",
        type="primary",
        icon=":material/download:",
        width="stretch",
    )
    c1, c2 = st.columns(2)
    full = c1.toggle("Open full itinerary", key="show_full")
    c2.button("Change details", icon=":material/auto_awesome:", width="stretch",
              on_click=go, args=("wizard", 1))
    if full:
        show_day_cards(ss.itinerary, dest)


# ---------------- Page ----------------
destinations = load_places()
api_key, model = get_settings()

ss = st.session_state
ss.setdefault("view", "home")
ss.setdefault("step", 1)
for key, default in {
    "w_days": 3, "w_budget": "Mid-range", "w_companions": "Solo", "w_pace": "Balanced",
    "w_stay": "No preference", "w_interests": [], "w_food": [],
}.items():
    ss.setdefault(key, default)

st.image(str(ASSETS / "logo.png"), width=150)

if not api_key:
    st.error("No GEMINI_API_KEY found in secrets. Add it to run the planner.")
    st.stop()

if ss.view == "plan" and "itinerary" in ss:
    show_plan(destinations, api_key, model)
elif ss.view == "wizard":
    show_wizard(destinations, api_key, model)
else:
    show_home(destinations)
