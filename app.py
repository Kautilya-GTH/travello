"""Travello — AI trip planner (MVP).

Workflow (one page, three views kept in st.session_state.view):
  home    -> hero + four destination cards
  intake  -> the Travello assistant asks the trip brief one question at a time
  plan    -> Gemini itinerary (day cards), edit by chat, download
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
TEAL = "#0E8585"

# Card text for the home screen (same copy as the team's prototype).
TAGLINES = {
    "kyoto": "Culture & calm",
    "bali": "A slower escape",
    "goa": "Coast & colour",
    "jaipur": "Heritage & discovery",
}
CARD_ORDER = ["kyoto", "bali", "goa", "jaipur"]

# The assistant's questions, in order. Each answer fills one field of the brief.
STEPS = ["travel_type", "destination", "days", "budget", "companions", "pace",
         "interests", "must_visit", "done"]
DAY_OPTIONS = [2, 3, 4, 5, 7, 10]
COMPANIONS = ["Solo", "Couple", "Friends", "Family"]
INTERESTS = ["Culture", "Nature", "Food", "Relaxation", "Shopping", "Adventure"]

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
    """An image from assets/ as a data URI, for the HTML photo blocks."""
    return "data:image/jpeg;base64," + base64.b64encode((ASSETS / name).read_bytes()).decode()


@st.cache_data
def load_stories():
    """Sample community stories. Their itineraries go through the same id
    validation as Gemini's, so a typo in stories.json can't show a fake place."""
    destinations = load_places()
    with open(ROOT / "data" / "stories.json", encoding="utf-8") as f:
        stories = json.load(f)["stories"]
    for s in stories:
        dest = destinations[s["destination"]]
        s["itinerary"], s["warnings"] = planner.validate(
            s["itinerary"], dest, len(s["itinerary"]["days"])
        )
    return stories


def lookup(dest):
    """id -> place dict, across every category of one destination."""
    return {p["id"]: p for cat in ("sights", "food", "stays", "extras") for p in dest[cat]}


def eyebrow(text):
    """Small teal capitals above a heading, like the prototype."""
    st.markdown(f':small[**:color[{text}]{{foreground="{TEAL}"}}**]')


def photo_block(image, height, inner_html, radius=18):
    """Photo with a dark fade and light text on top (like the prototype cards)."""
    st.html(f"""
    <div style="position:relative; height:{height}px; border-radius:{radius}px; overflow:hidden;
                background:url('{img_b64(image)}') center / cover;
                font-family:'Trebuchet MS','Segoe UI',sans-serif; color:#FFF7ED;">
      <div style="position:absolute; inset:0;
                  background:linear-gradient(180deg, rgba(16,42,67,0) 35%, rgba(16,42,67,.78) 100%);"></div>
      <div style="position:absolute; left:20px; right:20px; bottom:18px;">{inner_html}</div>
    </div>
    """)


# ---------------- Navigation (button callbacks) ----------------
def go_home():
    st.session_state.view = "home"


def go_community():
    st.session_state.view = "community"


def go(view):
    st.session_state.view = view


def open_traveller(author):
    st.session_state.traveller = author
    st.session_state.view = "traveller"


def nav_bar():
    """Top navigation like the prototype (Explore / Plan / Community / My trips / Profile)."""
    view = st.session_state.view
    st.image(str(ASSETS / "logo.png"), width=130)
    row = st.container(horizontal=True, vertical_alignment="center", gap="small")
    for label, views, action in (
        ("Explore", ("home",), go_home),
        ("Plan", ("intake", "plan"), start_intake),
        ("Community", ("community", "traveller"), go_community),
        ("My trips", ("trips",), lambda: go("trips")),
        ("Profile", ("profile",), lambda: go("profile")),
    ):
        row.button(label, key=f"nav_{label}", on_click=action,
                   type="primary" if view in views else "tertiary")


def start_intake(dest_key=None):
    """Open the assistant. A destination card skips the first two questions."""
    ss = st.session_state
    ss.view = "intake"
    ss.answers = {}
    ss.intake_error = ""
    ss.w_interests = []
    hello = "Hi! I'm your Travello assistant."
    if dest_key:
        d = load_places()[dest_key]
        ss.answers = {"destination": dest_key,
                      "travel_type": "Domestic" if d["domestic"] else "International"}
        ss.intake_step = "days"
        ss.intake_msgs = [("assistant", f"{hello} {d['name']} it is. " + question("days", ss.answers))]
    else:
        ss.intake_step = "travel_type"
        ss.intake_msgs = [("assistant", f"{hello} " + question("travel_type", ss.answers))]


# ---------------- Home ----------------
def show_home(destinations):
    eyebrow("YOUR NEXT CHAPTER")
    st.title(f'Plan less.  \n:color[*Experience more.*]{{foreground="{TEAL}"}}')
    st.write(
        "Tell us about your trip and get sightseeing, food and stay ideas, arranged day by "
        "day — then shape it your way."
    )
    st.button("Start planning your trip with AI", type="primary", icon=":material/auto_awesome:",
              width="stretch", on_click=start_intake)
    st.caption("AI helps. **You decide.**")

    photo_block("bali.jpg", 260, """
        <div style="font-size:12px; font-weight:700; letter-spacing:2px;">UBUD, BALI
          <span style="opacity:.75; font-weight:400;">&nbsp; 08°30′S · 115°15′E</span></div>
        <div style="font-size:28px; font-weight:700; line-height:1.15; margin-top:6px;">
          Slow mornings.</div>
        <div style="font-size:15px; opacity:.92;">There's room for those, too.</div>
    """, radius=22)

    st.space("medium")
    eyebrow("A GOOD PLACE TO BEGIN")
    st.header("Where will you go?")
    st.caption("Four places to begin. Plenty of room to make them your own.")

    for row, pair in enumerate((CARD_ORDER[:2], CARD_ORDER[2:])):
        cols = st.columns(2)
        for i, (col, key) in enumerate(zip(cols, pair)):
            d = destinations[key]
            with col:
                photo_block(f"{key}.jpg", 220, f"""
                    <div style="font-size:12px; opacity:.85;">0{row * 2 + i + 1} / 04</div>
                    <div style="font-size:13px; margin-top:4px;">{d['country']} · {TAGLINES[key]}</div>
                    <div style="font-size:26px; font-weight:700;">{d['name']}</div>
                """)
                st.button(f"Plan {d['name']}", key=f"card_{key}", icon=":material/arrow_forward:",
                          width="stretch", on_click=start_intake, args=(key,))

    st.space("medium")
    eyebrow("FROM THE TRAVELLER'S JOURNAL")
    head = st.container(horizontal=True, vertical_alignment="center")
    head.header("Good trips are better shared.")
    head.button("Meet the community", icon=":material/arrow_forward:", on_click=go_community)
    for story in load_stories()[:2]:
        story_card(story, destinations)

    st.divider()
    st.image(str(ASSETS / "logo.png"), width=110)
    st.caption("**PLAN LESS. EXPERIENCE MORE.** · Made for the journeys that stay with you.")
    st.caption("Profile and My trips are kept for this visit only — accounts come later.")


# ---------------- Community: sample traveller stories ----------------
def toggle_like(key):
    liked = st.session_state.setdefault("liked", set())
    liked.symmetric_difference_update({key})


def make_it_mine(story):
    """Copy a story's itinerary into the planner, where chat edits can change it."""
    ss = st.session_state
    ss.itinerary = json.loads(json.dumps(story["itinerary"]))  # own copy; the original stays as it is
    ss.warnings = []
    ss.dest_key = story["destination"]
    ss.brief = {**story["brief"], "days": len(story["itinerary"]["days"]),
                "interests": [], "food": [], "must_visit": ""}
    ss.source_label = f"{story['author']}'s shared itinerary"
    ss.trip_id = None
    ss.chat = [("assistant", "Your copy is ready. What would you like to change?")]
    ss.view = "plan"


def story_card(story, destinations):
    d = destinations[story["destination"]]
    days = len(story["itinerary"]["days"])
    liked = story["key"] in st.session_state.get("liked", set())
    with st.container(border=True):
        photo_block(f"{story['destination']}.jpg", 170, f"""
            <div style="font-size:12px; font-weight:700; letter-spacing:2px;">{d['name'].upper()}</div>
            <div style="font-size:13px; opacity:.9;">{days} DAYS · {'OPEN TO JOIN' if story['open_to_join'] else 'PREVIOUS TRIP'}</div>
        """, radius=14)
        initials = "".join(w[0] for w in story["author"].split()[:2])
        who = st.container(horizontal=True, vertical_alignment="center", gap="small")
        who.markdown(f":color-badge[{initials}]")
        who.button(story["author"], key=f"author_{story['key']}", type="tertiary",
                   on_click=open_traveller, args=(story["author"],), help="View profile")
        who.markdown(f":small[{story['handle']} · {story['home']}]")
        st.subheader(story["title"])
        st.write(story["summary"])
        st.caption(f"{days} days · {d['country']} · :gray-badge[Sample story]")
        row = st.container(horizontal=True, vertical_alignment="center")
        row.button(
            f"{story['likes'] + liked}", key=f"like_{story['key']}",
            icon=":material/favorite:" if liked else ":material/favorite_border:",
            type="tertiary", on_click=toggle_like, args=(story["key"],),
        )
        show = row.toggle("View itinerary", key=f"view_{story['key']}")
        row.button("Make it Mine", key=f"mine_{story['key']}", type="primary",
                   icon=":material/content_copy:", on_click=make_it_mine, args=(story,))
        if show:
            places = lookup(d)
            for day in story["itinerary"]["days"]:
                names = [places[i["id"]]["name"] for sl in planner.SLOTS for i in day[sl]]
                st.markdown(f"**Day {day['day']}** · {day['title']}  \n:small[{' · '.join(names) or 'Free time'}]")
            st.caption("Make it Mine opens your own copy in the planner. The original stays as it is.")


def show_traveller(destinations):
    """Read-only profile of a sample traveller, opened from a story."""
    author = st.session_state.get("traveller")
    stories = [s for s in load_stories() if s["author"] == author]
    st.button("Back to Community", icon=":material/arrow_back:", type="tertiary",
              on_click=go_community)
    if not stories:
        st.caption("This traveller couldn't be found.")
        return
    first = stories[0]
    eyebrow("SAMPLE TRAVELLER")
    initials = "".join(w[0] for w in author.split()[:2])
    st.title(f":color-badge[{initials}] {author}")
    st.caption(f"{first['handle']} · {first['home']}")
    st.info("This is a sample profile to show how Community works.", icon=":material/info:")
    c1, c2, c3 = st.columns(3)
    c1.metric("Trips shared", len(stories))
    c2.metric("Days of travel", sum(len(s["itinerary"]["days"]) for s in stories))
    c3.metric("Likes", sum(s["likes"] for s in stories))
    st.subheader("Trips")
    for story in stories:
        story_card(story, destinations)


# ---------------- My trips (kept for this visit only — no database) ----------------
def save_trip():
    """Save the plan on screen to My trips (or update it if it's already saved)."""
    ss = st.session_state
    trips = ss.setdefault("my_trips", {})
    if not ss.get("trip_id"):
        ss.trip_counter = ss.get("trip_counter", 0) + 1
        ss.trip_id = f"trip{ss.trip_counter}"
    trips[ss.trip_id] = {
        "dest_key": ss.dest_key,
        "brief": dict(ss.brief),
        "itinerary": json.loads(json.dumps(ss.itinerary)),
        "source_label": ss.get("source_label", ""),
    }
    ss.saved_note = "Saved to My trips."


def open_trip(trip_id):
    ss = st.session_state
    t = ss.my_trips[trip_id]
    ss.itinerary = json.loads(json.dumps(t["itinerary"]))
    ss.brief, ss.dest_key, ss.source_label = dict(t["brief"]), t["dest_key"], t["source_label"]
    ss.warnings, ss.trip_id = [], trip_id
    ss.chat = [("assistant", "Welcome back. What would you like to change?")]
    ss.view = "plan"


def remove_trip(trip_id):
    ss = st.session_state
    ss.my_trips.pop(trip_id, None)
    if ss.get("trip_id") == trip_id:
        ss.trip_id = None


def show_trips(destinations):
    trips = st.session_state.get("my_trips", {})
    eyebrow("YOUR LITTLE COLLECTION")
    st.title(f'Trips to :color[*remember.*]{{foreground="{TEAL}"}}')
    st.caption(
        "The plans you've saved, ready when you are. Without accounts they're kept for this "
        "visit only — download a trip to keep it."
    )
    if not trips:
        eyebrow("A FRESH PAGE")
        st.subheader("Nothing saved just yet.")
        st.caption("Start with a place that's been on your mind. The rest will follow.")
        st.button("Plan a trip", type="primary", icon=":material/auto_awesome:", on_click=start_intake)
        return
    for trip_id, t in reversed(list(trips.items())):
        d = destinations[t["dest_key"]]
        days = len(t["itinerary"]["days"])
        with st.container(border=True):
            photo_block(f"{t['dest_key']}.jpg", 140, f"""
                <div style="font-size:12px; letter-spacing:2px; font-weight:700;">SAVED PRIVATELY</div>
                <div style="font-size:24px; font-weight:700;">{d['name']} · {days} days</div>
            """, radius=14)
            st.caption(f"{t['brief']['pace']} pace · {t['brief']['budget']} · {t['brief']['companions']}"
                       + (f" · based on {t['source_label']}" if t["source_label"] else ""))
            row = st.container(horizontal=True)
            row.button("Open", key=f"open_{trip_id}", type="primary", icon=":material/map:",
                       on_click=open_trip, args=(trip_id,))
            row.download_button(
                "Download", data=itinerary_markdown(t["itinerary"], d, t["brief"]),
                file_name=f"travello-{t['dest_key']}-{days}-days.md", mime="text/markdown",
                key=f"dl_{trip_id}", icon=":material/download:",
            )
            row.button("Remove", key=f"rm_{trip_id}", type="tertiary", icon=":material/delete:",
                       on_click=remove_trip, args=(trip_id,))


# ---------------- Profile (kept for this visit only — no accounts) ----------------
def show_profile():
    ss = st.session_state
    profile = ss.get("profile")
    eyebrow("TRAVELLER PROFILE")
    if not profile or ss.get("editing_profile"):
        st.title("What should we call you?")
        st.caption("Kept for this visit only — there are no accounts in this version.")
        with st.form("profile_form"):
            p = profile or {}
            name = st.text_input("Your name", value=p.get("name", ""))
            username = st.text_input("Username", value=p.get("username", ""), placeholder="e.g. your.travel.story",
                                     help="3–20 letters, numbers, dots or underscores.")
            home = st.text_input("Home city", value=p.get("home", ""), placeholder="e.g. Kolkata, India")
            style = st.pills("What feels like you?", list(planner.PACE_ITEMS),
                             default=p.get("style"))
            budget = st.pills("Usual budget", list(planner.BUDGET_TIER), default=p.get("budget"))
            with_ = st.pills("Usually with", COMPANIONS, default=p.get("with"))
            if st.form_submit_button("Save profile", type="primary", width="stretch"):
                uname = username.strip().lstrip("@")
                if not name.strip():
                    st.warning("Please add your name.")
                elif not (3 <= len(uname) <= 20 and uname[0].isalpha()
                          and all(ch.isalnum() or ch in "._" for ch in uname)):
                    st.warning("Username: 3–20 characters, start with a letter; letters, numbers, dots or underscores.")
                else:
                    ss.profile = {"name": name.strip(), "username": uname, "home": home.strip(),
                                  "style": style, "budget": budget, "with": with_}
                    ss.editing_profile = False
                    st.rerun()
        if profile:
            st.button("Cancel", on_click=lambda: ss.update(editing_profile=False))
        return

    initials = "".join(w[0] for w in profile["name"].split()[:2]).upper()
    st.title(f":color-badge[{initials}] {profile['name']}")
    st.caption(f"@{profile['username']}" + (f" · {profile['home']}" if profile["home"] else ""))
    tags = [t for t in (profile["style"] and f"{profile['style']} pace", profile["budget"],
                        profile["with"] and f"Usually {profile['with'].lower()}") if t]
    if tags:
        st.markdown(" ".join(f":blue-badge[{t}]" for t in tags))
    trips = ss.get("my_trips", {})
    c1, c2 = st.columns(2)
    c1.metric("Trips saved", len(trips))
    c2.metric("Days planned", sum(len(t["itinerary"]["days"]) for t in trips.values()))
    row = st.container(horizontal=True)
    row.button("Edit profile", icon=":material/edit:", on_click=lambda: ss.update(editing_profile=True))
    row.button("View My trips", icon=":material/bookmark:", on_click=lambda: go("trips"))
    st.caption("Trips — only you can see these. Profile and trips are kept for this visit only.")


def show_community(destinations):
    eyebrow("THE GOOD PLACES ARE BETTER SHARED")
    st.title(f'Travel lives here. :color[*Stories and journals.*]{{foreground="{TEAL}"}}')
    st.caption("Real itineraries, little discoveries, and people who love to go.")
    st.info(
        "These are sample stories to show how shared trips look. Publishing, comments and "
        "join requests need accounts, which come with My trips and Profile later.",
        icon=":material/info:",
    )
    names = {k: destinations[k]["name"] for k in CARD_ORDER}
    pick = st.pills("Filter traveller stories", list(names), format_func=names.get,
                    key="story_filter")
    stories = [s for s in load_stories() if not pick or s["destination"] == pick]
    if not stories:
        st.caption(f"No stories for {names[pick]} yet. Plan yours and it could be the first.")
    for story in stories:
        story_card(story, destinations)


# ---------------- Intake: the assistant asks, the user taps or types ----------------
def question(step, a):
    places = load_places()
    name = places[a["destination"]]["name"] if a.get("destination") else "there"
    return {
        "travel_type": "Is this a domestic or an international trip?",
        "destination": "Lovely! Where in India would you like to go?"
        if a.get("travel_type") == "Domestic" else "Where abroad would you like to go?",
        "days": f"{name} — great choice. How many days do you have?",
        "budget": "What kind of budget are you thinking?",
        "companions": "Who are you travelling with?",
        "pace": "What pace suits you?",
        "interests": "What are you into? Pick a few, then tap Done.",
        "must_visit": "Any must-visit places? Type them, or tap Skip.",
        "done": (
            f"All set: {a.get('days')} days in {name}, {str(a.get('budget', '')).lower()} budget, "
            f"{str(a.get('companions', '')).lower()}, {str(a.get('pace', '')).lower()} pace. "
            "Tap below and I'll plan your days."
        ),
    }[step]


def step_options(step, a):
    """Tap options for the current question as (label, value) pairs."""
    places = load_places()
    if step == "travel_type":
        return [("Domestic", "Domestic"), ("International", "International")]
    if step == "destination":
        domestic = a.get("travel_type") == "Domestic"
        return [(d["name"], k) for k, d in places.items() if d["domestic"] == domestic]
    if step == "days":
        return [(f"{n} days", n) for n in DAY_OPTIONS]
    if step == "budget":
        return [(b, b) for b in planner.BUDGET_TIER]
    if step == "companions":
        return [(c, c) for c in COMPANIONS]
    if step == "pace":
        return [(p, p) for p in planner.PACE_ITEMS]
    if step == "must_visit":
        return [("Skip", "")]
    return []


def answer(label, value):
    """Record one answer, then ask the next question."""
    ss = st.session_state
    step = ss.intake_step
    ss.answers[step] = value
    ss.intake_error = ""
    nxt = STEPS[STEPS.index(step) + 1]
    ss.intake_step = nxt
    ss.intake_msgs += [("user", label), ("assistant", question(nxt, ss.answers))]


def answer_typed(text):
    """Understand a typed answer by matching it to the current question's options."""
    ss = st.session_state
    step, low = ss.intake_step, text.strip().lower()
    if step == "must_visit":
        return answer(text.strip()[:200], text.strip()[:200])
    if step == "interests":
        picked = [i for i in INTERESTS if i.lower() in low]
        if picked:
            return answer(", ".join(picked), picked)
        ss.intake_error = "Tap a few interests, then Done."
        return
    if step == "days":
        digits = "".join(ch for ch in low if ch.isdigit())
        n = 7 if "week" in low and not digits else int(digits) if digits else 0
        if 2 <= n <= 10:
            return answer(f"{n} days", n)
        ss.intake_error = "Trips can be 2 to 10 days — type a number."
        return
    for label, value in step_options(step, ss.answers):
        if label.lower() in low:
            return answer(label, value)
    ss.intake_error = "Please pick one of the options."


def show_intake(destinations, api_key, model):
    ss = st.session_state
    typed = st.chat_input("Tap an option or type your answer…")
    if typed and ss.intake_step != "done":
        answer_typed(typed)

    st.button("Back to Explore", icon=":material/arrow_back:", type="tertiary", on_click=go_home)
    eyebrow("01 / 02 · TRIP DETAILS")
    st.title(f'Let\'s make a little room for :color[*somewhere.*]{{foreground="{TEAL}"}}')
    st.caption(
        "Chat with your Travello assistant. It'll ask a few questions, then plan places to see, "
        "eat and stay — and you can change anything after."
    )

    with st.container(border=True):
        st.markdown("**Travello assistant**  \n:small[AI suggestions — always double-check before booking]")
        for role, text in ss.intake_msgs:
            avatar = str(ASSETS / "pin.png") if role == "assistant" else ":material/person:"
            with st.chat_message(role, avatar=avatar):
                st.write(text)

        step = ss.intake_step
        if step == "interests":
            st.pills("Interests", INTERESTS, selection_mode="multi", key="w_interests",
                     label_visibility="collapsed")
            picked = ss.w_interests or []
            st.button("Done", type="primary", disabled=not picked, on_click=answer,
                      args=(", ".join(picked), picked))
        elif step == "done":
            if st.button("Plan my days", type="primary", icon=":material/arrow_forward:",
                         width="stretch"):
                generate(destinations, api_key, model)
        else:
            row = st.container(horizontal=True)
            for label, value in step_options(step, ss.answers):
                row.button(label, key=f"opt_{step}_{label}", on_click=answer, args=(label, value))
        if ss.intake_error:
            st.warning(ss.intake_error)


def generate(destinations, api_key, model):
    ss = st.session_state
    a = ss.answers
    brief = {
        "days": a["days"],
        "budget": a["budget"],
        "companions": a["companions"],
        "pace": a["pace"],
        "interests": a.get("interests") or [],
        "food": [],
        "must_visit": a.get("must_visit", ""),
    }
    with st.spinner(f"Finding places to see, eat and stay in {destinations[a['destination']]['name']}…"):
        try:
            itin, warnings = planner.generate_itinerary(
                get_client(api_key), model, brief, destinations[a["destination"]]
            )
        except planner.PlannerError as e:
            st.error(str(e))
            return
    # Kept in session_state so later edits build on the latest version.
    ss.itinerary, ss.warnings, ss.brief, ss.dest_key = itin, warnings, brief, a["destination"]
    ss.chat = [("assistant", "Your plan is ready. What would you like to change?")]
    ss.source_label = ""
    ss.trip_id = None  # a new plan, not yet in My trips
    ss.view = "plan"
    st.rerun()


# ---------------- Plan ----------------
def show_day_cards(itin, dest):
    places = lookup(dest)
    for day in itin["days"]:
        with st.container(border=True):
            st.subheader(f"Day {day['day']}" + (f" · {day['title']}" if day["title"] else ""))
            for slot in planner.SLOTS:
                st.markdown(f':small[**:color[{slot.upper()}]{{foreground="{TEAL}"}}**]')
                if not day[slot]:
                    st.markdown("- _Free time_")
                for item in day[slot]:
                    p = places[item["id"]]
                    extra = p.get("dur") or p.get("price") or ""
                    line = f"- **{p['name']}**" + (f" ({extra})" if extra else "")
                    line += f" — {item['note'] or p['note']}"
                    st.markdown(line)


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
    ss.chat.append(("user", request))
    with st.spinner("Reworking your plan…"):
        try:
            itin, warnings, changes = planner.edit_itinerary(
                get_client(api_key), model, ss.brief, dest, ss.itinerary, request
            )
        except planner.PlannerError as e:
            ss.chat.append(("assistant", f"Something went wrong on my side ({e}) Your plan hasn't changed."))
            return
    ss.itinerary, ss.warnings = itin, warnings
    ss.brief = {**ss.brief, "days": len(itin["days"])}
    ss.chat.append(("assistant", changes or "Done — your plan is updated."))


def show_plan(destinations, api_key, model):
    ss = st.session_state
    dest = destinations[ss.dest_key]
    itin = ss.itinerary

    # Pinned to the bottom of the page: the edit-by-chat box.
    request = st.chat_input("e.g. Make day 2 more relaxed, add a sunset spot")
    if request:
        apply_edit(request, dest, api_key, model)
        itin = ss.itinerary

    top = st.container(horizontal=True, vertical_alignment="center")
    top.button("Edit trip details", icon=":material/arrow_back:", type="tertiary",
               on_click=start_intake, args=(ss.dest_key,))
    top.caption("02 / 02 · DRAFT — download it to keep a copy")

    eyebrow(f"{dest['country'].upper()} / {len(itin['days'])} DAYS / {ss.brief['pace'].upper()} PACE")
    st.title(f'{dest["name"]}, :color[*your way.*]{{foreground="{TEAL}"}}')
    if ss.get("source_label"):
        st.caption(f"Your own copy, based on {ss.source_label}. Changes here never affect the original.")
    if itin["summary"]:
        st.write(itin["summary"])

    places = lookup(dest)
    stay = itin["stay"]
    with st.container(border=True):
        if stay:
            s = places[stay["id"]]
            st.markdown(
                f":material/hotel: **Your stay:** {s['name']} — {stay['note'] or s['note']} · "
                f"{s['type']} · around ₹{s['price']:,}/night · ⭐ {s['rating']}"
            )
        else:
            st.markdown(":material/hotel: **Your stay:** none could be matched — try asking for one below.")
        st.caption("Sample stay · not a verified listing or booking.")

    for w in ss.warnings:
        st.warning(w)
    show_day_cards(itin, dest)
    st.caption(
        "AI suggestions aren't checked against live sources. Confirm opening hours, safety "
        "advice and bookings before you go."
    )

    saved = ss.get("trip_id") in ss.get("my_trips", {})
    st.button("Update in My trips" if saved else "Save itinerary to My trips", type="primary",
              icon=":material/check:", width="stretch", on_click=save_trip)
    if ss.pop("saved_note", ""):
        st.success("Saved to My trips (kept for this visit — download to keep a copy).",
                   icon=":material/bookmark_added:")
    st.download_button(
        "Download itinerary",
        data=itinerary_markdown(itin, dest, ss.brief),
        file_name=f"travello-{ss.dest_key}-{len(itin['days'])}-days.md",
        mime="text/markdown",
        icon=":material/download:",
        width="stretch",
    )

    with st.container(border=True):
        eyebrow("TRAVELLO ASSISTANT")
        for role, text in ss.chat:
            avatar = str(ASSETS / "pin.png") if role == "assistant" else ":material/person:"
            with st.chat_message(role, avatar=avatar):
                st.write(text)
        st.caption("Type a change in the box at the bottom of the page.")


# ---------------- Page ----------------
destinations = load_places()
api_key, model = get_settings()

ss = st.session_state
ss.setdefault("view", "home")

nav_bar()

if not api_key:
    st.error("No GEMINI_API_KEY found in secrets. Add it to run the planner.")
    st.stop()

if ss.view == "plan" and "itinerary" in ss:
    show_plan(destinations, api_key, model)
elif ss.view == "intake" and "intake_step" in ss:
    show_intake(destinations, api_key, model)
elif ss.view == "community":
    show_community(destinations)
elif ss.view == "traveller":
    show_traveller(destinations)
elif ss.view == "trips":
    show_trips(destinations)
elif ss.view == "profile":
    show_profile()
else:
    show_home(destinations)
