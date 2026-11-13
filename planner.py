"""Travello planner — talks to Gemini and keeps its answers honest.

Everything Gemini-related lives here so app.py only deals with the UI.
Flow: build a prompt from the trip brief + curated places -> ask Gemini
for JSON -> parse it safely -> keep only ids that exist in places.json.
"""
import json
import time

import streamlit as st
from google.genai import errors, types

SLOTS = ("morning", "afternoon", "evening")

# Retry settings for when Gemini is overloaded (429 = rate limit, 503 = busy).
MAX_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 2
BUSY_CODES = (429, 503)
TIMEOUT_CODE = 504  # model didn't answer within the client timeout (set in app.py)

# Pace -> how many places/meals per day in total (all three slots together).
PACE_ITEMS = {
    "Relaxed": "2 to 3",
    "Balanced": "3 to 4",
    "Activity-filled": "5 to 6",
}

# Budget -> which stay tier to recommend (tier field in places.json).
BUDGET_TIER = {"Budget": 1, "Mid-range": 2, "Premium": 3}


class PlannerError(Exception):
    """A problem we can show to the user as a friendly message."""


def _place_list(dest):
    """Compact view of the destination data for the prompt (ids are the key part)."""
    lines = []
    for cat in ("sights", "food", "extras"):
        lines.append(f"{cat.upper()}:")
        for p in dest[cat]:
            tags = ", ".join(p.get("tags", []))
            lines.append(f"- id={p['id']} | {p['name']} | tags: {tags} | {p['note']}")
    lines.append("STAYS:")
    for s in dest["stays"]:
        lines.append(
            f"- id={s['id']} | {s['name']} | {s['type']} | tier {s['tier']} | "
            f"INR {s['price']}/night | {s['note']}"
        )
    return "\n".join(lines)


def _rules(dest):
    return f"""You are Travello, a trip planner for {dest['name']}, {dest['country']}.

RULES
- Use ONLY places from the list below, referenced by their exact id. Never invent places.
- Each day has morning, afternoon and evening slots. Each slot is a list of
  items; an empty list means free time.
- Do not repeat a sight or extra across days. Food places may repeat only if the
  list runs out. If you run out of places, leave slots empty rather than inventing.
- Pick exactly one stay from STAYS.
- Keep every "note" under 20 words: why this fits the traveller or a practical tip.

PLACES FOR {dest['name'].upper()}
{_place_list(dest)}

Return JSON only, in exactly this shape:
{{
  "summary": "one or two sentences describing the trip",
  "stay": {{"id": "<stay id>", "note": "why this stay fits"}},
  "days": [
    {{"day": 1, "title": "short theme for the day",
      "morning":   [{{"id": "<place id>", "note": "..."}}],
      "afternoon": [{{"id": "<place id>", "note": "..."}}],
      "evening":   [{{"id": "<place id>", "note": "..."}}]}}
  ]
}}"""


def _brief_text(brief):
    tier = BUDGET_TIER[brief["budget"]]
    return f"""TRAVELLER BRIEF
- Days: {brief['days']} (return exactly {brief['days']} day objects)
- Budget: {brief['budget']} -> recommend a tier {tier} stay
- Travelling as: {brief['companions']}
- Pace: {brief['pace']} -> {PACE_ITEMS[brief['pace']]} items per day in total, including meals
- Interests: {', '.join(brief['interests']) or 'no preference'} (prefer places with these tags)
- Food preferences: {', '.join(brief['food']) or 'no preference'} (prefer food places with these tags)"""


def _call_with_retry(client, model, prompt):
    """Call one model up to MAX_ATTEMPTS times, retrying only on 429/503 (busy).

    Returns the response, or None if the model is busy or timed out.
    A timeout (504) gives up on this model at once rather than waiting again.
    Any other error (bad key, bad request...) is raised straight away.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
        except errors.APIError as e:
            if e.code == TIMEOUT_CODE:
                return None
            if e.code not in BUSY_CODES:
                raise
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_WAIT_SECONDS * attempt)  # wait 2s, then 4s
    return None


def _fallback_model():
    """Second model to try when the main one is busy (optional secret)."""
    try:
        return st.secrets.get("GEMINI_FALLBACK_MODEL")
    except Exception:  # no secrets.toml at all
        return None


def _ask_gemini(client, model, prompt):
    """Call Gemini asking for JSON and return the parsed dict."""
    try:
        resp = _call_with_retry(client, model, prompt)
        fallback = _fallback_model()
        if resp is None and fallback and fallback != model:
            resp = _call_with_retry(client, fallback, prompt)
    except Exception as e:
        raise PlannerError(f"Couldn't reach Gemini ({type(e).__name__}). Please try again.") from e
    if resp is None:
        raise PlannerError("Gemini is busy, please try again in a minute.")

    try:
        data = json.loads(resp.text or "")
    except json.JSONDecodeError as e:
        raise PlannerError("Gemini sent back something we couldn't read. Please try again.") from e
    if not isinstance(data, dict) or not isinstance(data.get("days"), list):
        raise PlannerError("Gemini's plan was missing the day-by-day section. Please try again.")
    return data


def validate(data, dest, num_days):
    """Keep only ids that exist in places.json. Returns (itinerary, warnings).

    This is the guard against invented places: anything Gemini makes up is
    dropped here and reported, so the UI only ever shows curated entries.
    """
    activity_ids = {p["id"] for cat in ("sights", "food", "extras") for p in dest[cat]}
    stay_ids = {s["id"] for s in dest["stays"]}
    warnings = []

    days = []
    for i, raw_day in enumerate(data["days"][:num_days], start=1):
        raw_day = raw_day if isinstance(raw_day, dict) else {}
        day = {"day": i, "title": str(raw_day.get("title", ""))}
        for slot in SLOTS:
            items = []
            for item in raw_day.get(slot) or []:
                pid = item.get("id") if isinstance(item, dict) else None
                if pid in activity_ids:
                    items.append({"id": pid, "note": str(item.get("note", ""))})
                else:
                    warnings.append(f"Day {i} {slot}: dropped unknown place '{pid}'.")
            day[slot] = items
        days.append(day)

    if len(days) < num_days:
        warnings.append(f"Gemini planned {len(days)} of {num_days} days.")

    raw_stay = data.get("stay") if isinstance(data.get("stay"), dict) else {}
    stay = None
    if raw_stay.get("id") in stay_ids:
        stay = {"id": raw_stay["id"], "note": str(raw_stay.get("note", ""))}
    else:
        warnings.append(f"Dropped unknown stay '{raw_stay.get('id')}'.")

    itinerary = {"summary": str(data.get("summary", "")), "stay": stay, "days": days}
    return itinerary, warnings


def generate_itinerary(client, model, brief, dest):
    """Step 2 of the workflow: brief + curated places -> validated itinerary."""
    prompt = _rules(dest) + "\n\n" + _brief_text(brief)
    data = _ask_gemini(client, model, prompt)
    return validate(data, dest, brief["days"])
