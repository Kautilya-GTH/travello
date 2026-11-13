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
    "Slow": "2 to 3",
    "Balanced": "3 to 4",
    "Full": "5 to 6",
}

# Budget -> which stay tier to recommend (tier field in places.json has 1-3,
# so Comfort and Luxury both map to the top tier).
BUDGET_TIER = {"Budget": 1, "Mid-range": 2, "Comfort": 3, "Luxury": 3}


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


def _brief_text(brief, editing=False):
    tier = BUDGET_TIER[brief["budget"]]
    days = (
        f"{brief['days']} (keep this number unless the change request asks for a "
        "different number of days, between 2 and 10)"
        if editing
        else f"{brief['days']} (return exactly {brief['days']} day objects)"
    )
    stay_type = brief.get("stay_type", "No preference")
    stay_line = (
        f"- Stay type: prefer a {stay_type} if one exists in the right tier"
        if stay_type != "No preference"
        else "- Stay type: no preference"
    )
    must = brief.get("must_visit", "").strip()
    must_line = (
        f"- Must-visit wishes: \"{must}\" (include matching places from the list; "
        "ignore anything not in the list)"
        if must
        else "- Must-visit wishes: none"
    )
    # Choices from the "Choose what goes in" step (ids from places.json).
    picks = []
    if brief.get("include_ids"):
        picks.append(f"- MUST include these ids: {', '.join(brief['include_ids'])} "
                     "(spread them sensibly; if they don't all fit, keep as many as the pace allows)")
    if brief.get("skip_ids"):
        picks.append(f"- NEVER use these ids (the traveller skipped them): {', '.join(brief['skip_ids'])}")
    if brief.get("stay_id"):
        picks.append(f"- Use this stay id (the traveller chose it): {brief['stay_id']}")
    picks_text = ("\n" + "\n".join(picks)) if picks else ""
    return f"""TRAVELLER BRIEF
- Days: {days}
- Budget: {brief['budget']} -> recommend a tier {tier} stay
{stay_line}
{must_line}{picks_text}
- Travelling as: {brief['companions']}
- Pace: {brief['pace']} -> {PACE_ITEMS[brief['pace']]} items per day in total, including meals
- Interests: {', '.join(brief['interests']) or 'no preference'} (prefer places with these tags)
- Food preferences: {', '.join(brief['food']) or 'no preference'} (prefer food places with these tags)"""


def _call_with_retry(client, model, prompt, json_mode):
    """Call one model up to MAX_ATTEMPTS times, retrying only on 429/503 (busy).

    Returns the response, or None if the model is busy or timed out.
    A timeout (504) gives up on this model at once rather than waiting again.
    Any other error (bad key, bad request...) is raised straight away.
    """
    config = types.GenerateContentConfig(response_mime_type="application/json") if json_mode else None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return client.models.generate_content(model=model, contents=prompt, config=config)
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


def call_gemini(client, model, prompt, json_mode=True):
    """Main model with retries, then the fallback model. Returns (response, model_used).

    Raises PlannerError with a friendly message if neither model answers.
    """
    try:
        resp = _call_with_retry(client, model, prompt, json_mode)
        fallback = _fallback_model()
        if resp is None and fallback and fallback != model:
            model = fallback
            resp = _call_with_retry(client, model, prompt, json_mode)
    except Exception as e:
        raise PlannerError(f"Couldn't reach Gemini ({type(e).__name__}). Please try again.") from e
    if resp is None:
        raise PlannerError("Gemini is busy, please try again in a minute.")
    return resp, model


def _ask_gemini(client, model, prompt):
    """Call Gemini asking for JSON and return the parsed dict."""
    resp, _ = call_gemini(client, model, prompt)

    try:
        data = json.loads(resp.text or "")
    except json.JSONDecodeError as e:
        raise PlannerError("Gemini sent back something we couldn't read. Please try again.") from e
    if not isinstance(data, dict) or not isinstance(data.get("days"), list):
        raise PlannerError("Gemini's plan was missing the day-by-day section. Please try again.")
    return data


def validate(data, dest, num_days, exclude=()):
    """Keep only ids that exist in places.json. Returns (itinerary, warnings).

    This is the guard against invented places: anything Gemini makes up is
    dropped here and reported, so the UI only ever shows curated entries.
    Ids in `exclude` (places the traveller skipped) are removed too.
    """
    activity_ids = {p["id"] for cat in ("sights", "food", "extras") for p in dest[cat]}
    activity_ids -= set(exclude)
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
                elif pid in exclude:
                    warnings.append(f"Day {i} {slot}: removed '{pid}' because you skipped it.")
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
    return validate(data, dest, brief["days"], exclude=brief.get("skip_ids", ()))


def edit_itinerary(client, model, brief, dest, itinerary, request):
    """Step 3 of the workflow: current itinerary + the user's change -> updated itinerary.

    Gemini returns the FULL updated plan (same JSON shape) plus a one-line
    "changes" summary. The result goes through the same id validation as a
    new plan. Returns (itinerary, warnings, changes).
    """
    prompt = (
        _rules(dest)
        + "\n\n" + _brief_text(brief, editing=True)
        + "\n\nCURRENT ITINERARY (JSON)\n" + json.dumps(itinerary, ensure_ascii=False)
        + f"\n\nCHANGE REQUEST FROM THE TRAVELLER\n{request}\n\n"
        "Apply the change and return the FULL updated itinerary in the same JSON shape. "
        "Keep everything the traveller did not ask to change. "
        'Also add a top-level "changes" field: one short sentence saying what you changed. '
        "If the request can't be done with the listed places, keep the plan and explain "
        'why in "changes".'
    )
    data = _ask_gemini(client, model, prompt)
    num_days = max(2, min(10, len(data["days"])))  # the request may change the trip length
    itinerary, warnings = validate(data, dest, num_days)  # an edit may bring back a skipped place on request
    return itinerary, warnings, str(data.get("changes", "")).strip()
