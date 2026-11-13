# Travello
Plan less. Experience more.

Live app: https://travello-planner.streamlit.app/

## The problem

Independent travellers often find it tiring and time-consuming to plan trips because they search across multiple platforms, evaluate many options and arrange selected places into a day-wise schedule. Inspiration and information may be spread across Google Maps, Instagram, YouTube, Notes, Excel and WhatsApp.

Who it's for: Independent leisure traveller planning their own trip.

Evidence from our customer discovery (10 user interviews):
- 10/10 respondents said creating travel itineraries is tiring.
- Main difficulty: researching places and arranging them day-wise.
- Planning preference: a combination of AI assistance and personal control.
- "I have to search on so many platforms to plan my travel."

## How it works

1. Trip brief. A chat-style Travello assistant asks one question at a time, and the user
   taps an option or types an answer: domestic or international trip, destination, trip
   length (2–10 days), budget (Budget, Mid-range, Comfort or Luxury), who they're travelling
   with, pace (Slow, Balanced or Full), interests and any must-visit places. The destination
   is found with a search box: Domestic shows only places in India and International only
   places abroad. Starting from a destination card on the home page skips the first two
   questions.

2. Choose what goes in. The app lists sightseeing, cafés and food, and stays for the
   destination, with places that match the chosen interests first and stays in the chosen
   budget first. The user can include or skip each place, choose a stay, and open any place
   on Google Maps. For Goa, Jaipur, Kyoto and Bali the list comes from Travello's curated
   `data/places.json`. For any other destination, Gemini suggests the list, and the app
   labels these places as AI-suggested and not verified.

3. Gemini plans the trip. The app sends Gemini the brief, the user's choices and the
   destination's place list. The prompt tells Gemini to use only places from this list (by
   id), fill morning, afternoon and evening slots, match the number of activities to the
   chosen pace, prefer places that match the chosen interests, include the places the user
   included and any must-visit places on the list, never use skipped places, avoid repeating
   sights and extras, use the chosen stay or pick one in the right budget tier, and reply in
   JSON.

4. The app checks the answer. `validate()` in `planner.py` compares every place and stay
   id against the destination's place list. Anything not on the list, or skipped by the
   user, is removed and shown as a warning, and it keeps exactly the number of days
   requested. Unreadable replies show a friendly error, and if Gemini is busy or out of
   quota the app retries or switches to a fallback model.

5. The user gets a day-by-day plan. A short trip summary, one card per day with themed
   morning, afternoon and evening activities (duration or price plus a note on why it fits),
   and a recommended stay with type, price per night and rating. Stays are marked as sample
   listings, not real bookings.

6. Edit and keep it. The user can ask for changes in chat (for example "make Day 2 more
   relaxed" or "make it 4 days"); the updated plan goes through the same place check. The
   plan can be saved to My trips, where it can be reopened, edited, downloaded or removed,
   and it can be downloaded as a Markdown file.

7. Community and Profile. A read-only Community page shows sample traveller stories that
   can be filtered by destination, liked and opened day by day. Tapping an author opens
   their sample traveller profile. "Make it Mine" copies a story's itinerary into the
   planner as the user's own copy, where it can be edited and saved. The user can also set
   up their own profile (name, username, home city and travel style), which shows their
   saved trips. Without accounts, likes, My trips and Profile are kept for the current
   visit only.

## What's built in this MVP (PRD requirement IDs)

| Requirement | Status |
|---|---|
| AI-01 Trip intake | Built (chat-style assistant, one question at a time, tap or type, destination search for India or abroad). Includes must-visit places; exact dates and food preferences not included |
| AI-02 Recommendations | Built: separate "Choose what goes in" step with include/skip, stay choice and Google Maps links |
| AI-03 Day-wise itinerary | Built |
| AI-04 Conversational editing | Built (can also change trip length) |
| AI-05 Save to My Trips | Built, kept for the current visit only (no accounts or storage); download to keep a copy |
| COM-01 to COM-06 Community and Make It Mine | Partly: read-only Community page with sample stories, destination filter, likes, itinerary view, sample traveller profiles and Make It Mine; own profile kept for the current visit. Publishing, comments, follow and join requests not built — roadmap |

## Limitations

- Only four destinations (Goa, Jaipur, Kyoto and Bali) use Travello's curated, checked
  place data. Places for any other destination are AI-suggested and not verified.
- Destination search depends on a free OpenStreetMap search service and may occasionally
  be slow or unavailable.
- Stays are sample listings; prices for international destinations are approximate (INR).
- No live booking, payment processing or reservation management.
- No guaranteed live availability, opening hours, prices, traffic or weather.
- Nothing is saved between sessions: My trips, Profile and likes reset when the page
  reloads; the plan can be downloaded instead.
- Community shows sample stories only.
- Gemini can occasionally be busy, slow or out of free-tier quota, and results can vary
  between runs.

## Roadmap

| Release | Focus |
|---|---|
| Next iteration | Sign-in and permanent storage for My Trips and profiles, full Community (publishing trips, comments, follow, join requests), more curated destinations and checks for AI-suggested places |
| Enhancements | Route optimization, budget management, richer food/accommodation recommendations and weather-aware updates |
| Integrations | Booking integrations, live availability, alerts and advanced community safety features |

## Privacy and responsible AI

- Who benefits: travellers seeking reduced planning effort, relevant discovery and connections around trips.
- Who may be harmed: travellers affected by inaccurate information, privacy exposure or unsafe community interactions if safeguards are inadequate.
- The app has no accounts and stores no personal data. The trip brief, including typed
  answers, place choices and chat edit requests, is sent to the Gemini API to suggest
  places and generate and edit the plan. Destination searches are sent to the OpenStreetMap
  search service (Photon). Profile details stay in the current browser session and are not
  sent to Gemini.
- For the four curated destinations, Gemini can only use checked places. For other
  destinations, AI-suggested places are clearly labelled as not verified and link to Google
  Maps. Stays are labelled as samples, to reduce inaccurate recommendations.
- Community stories and traveller profiles are fictional samples and are labelled as such.

AI use disclosure
We used the following AI tools in this project:
Claude (claude.ai chat, Anthropic)
- Reviewed the course guidelines and our prototype and suggested a deployment plan.
- Wrote the first skeleton version of the app and extracted the destination data from our
  prototype into `data/places.json`.
- Wrote the project brief files for the coding assistant (`CLAUDE.md`, `REDESIGN.md`) and
  the theme file.
- Helped with setup and troubleshooting (Python, Git, GitHub, Streamlit Cloud, Gemini API key).
- Reviewed the code for compliance with the project rules.
- Assembled this README from our PRD, wrote the "How it works" section, and drafted this
  disclosure, which we reviewed and edited.

Claude Code (in VS Code, Anthropic)
- Wrote and debugged most of `app.py` and `planner.py`: the trip wizard, Gemini prompts,
  JSON parsing, place-id validation, chat edits, download, retry/fallback handling and the
  visual design. A dated log is in `AI_ASSIST_LOG.md`.

Google Gemini API
- Part of the product itself: it generates and edits itineraries for users.

Prototype, PRD and images
- We created the Prototype first in the Lovable app and provided it to users for Feedback.
- We wrote the PRD after accumulating all the data and put it in the Word Doc.
- Logo was created using Chatgpt and Images were downloaded from Google Photos.

What the team did
- The team disctributed the Prototype within friends circle for feedback.

We reviewed all AI-generated code and content, tested the app ourselves, and take
responsibility for everything submitted.

Team — Group 5
Name	Roll no.
Kumar Kautilya	2560034
Nisha Kumari	2560041
Hrishabh Singh	2560030
Sital Suman Rath	2560065
Prayash	2560047

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then add your key
streamlit run app.py


