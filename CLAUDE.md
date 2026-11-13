# Travello — project brief for Claude

## What this is
Group project for the Digital Product Management (DPM) course, EMBA at IIM Visakhapatnam.
Phase 2 asks for a minimum viable GenAI product: one target user, one problem, one use case,
one workflow, one AI capability, deployed with a live public link.

**Deadline: 9 PM IST, 13 Nov 2026.** Keep everything small and working. The course says
building more than asked earns no extra marks, so do not add features beyond the scope below.

## Mandatory tech stack (course rule, do not change)
- Python + Streamlit
- Deployed on Streamlit Cloud (free) from GitHub repo `Kautilya-GTH/travello`, branch `main`
- Gemini API via the `google-genai` package (`from google import genai`)
- No user authentication, no database, no multiple user roles, no second AI capability
- The AI must sit inside the product workflow, not be a standalone chatbot

## The product
Travello is an AI trip planner. The original prototype (a single HTML file) had 16 features
including a community feed, profiles and "Make it Mine". For the MVP we build ONLY the
AI Trip Planning flow. Everything else is a V2 roadmap item and must not be coded.

### MVP workflow (in order)
1. **Trip brief form** — destination (Goa, Jaipur, Kyoto, Bali), number of days (2–10),
   budget, travel companions, pace (Relaxed / Balanced / Activity-filled), interests,
   food preferences.
2. **Generate itinerary** — send the brief plus the destination's entries from
   `data/places.json` to Gemini. Gemini returns JSON: a day-wise plan with morning,
   afternoon and evening slots, plus one recommended stay. Show it as readable day cards.
3. **Edit by chat** — the user types a change ("make Day 2 lighter", "cheaper stay",
   "swap the fort for something with food"). Send the current itinerary JSON and the request
   to Gemini; it returns the full updated itinerary JSON. Re-render and say what changed.
4. **Download** — let the user download the final itinerary (text or markdown).

### AI design rules
- Gemini may ONLY use places, food, stays and extras that exist in `data/places.json`,
  referenced by their `id`. Validate the returned ids in Python and drop or flag anything
  not in the list. This prevents invented places.
- Request structured JSON output and parse it safely; on a parse failure, show a friendly
  error and let the user retry instead of crashing.
- Respect the brief: pace controls activities per day, budget controls stay tier,
  interests and food tags drive which places are chosen.
- Stays are sample listings, not verified bookings — show that disclaimer in the UI.
- Keep the itinerary in `st.session_state` so edits build on the latest version.

## Repo layout
```
app.py                          Streamlit UI
planner.py                      Gemini prompts, JSON parsing, id validation
data/places.json                curated destination data (do not invent new entries)
requirements.txt                streamlit, google-genai
.streamlit/secrets.toml         local only, git-ignored (GEMINI_API_KEY, GEMINI_MODEL)
.streamlit/secrets.toml.example template that IS committed
README.md
```

## Secrets
- Read the key with `st.secrets["GEMINI_API_KEY"]` and the model with
  `st.secrets.get("GEMINI_MODEL", ...)`.
- Never print, log, hard-code or commit the key. Before every commit, run `git status` and
  confirm `.streamlit/secrets.toml` and `.venv/` are not staged.

## Build steps
- [x] Step 1: skeleton app, places.json, deploy test with "Test Gemini" button
- [x] Step 2: trip brief form + itinerary generation (planner.py) + day-card display
- [ ] Step 3: chat-based edits
- [x] Step 4: download, error handling, light polish; remove the "Test Gemini" button
- [ ] Step 5: test with 2–3 real users, fix issues, push, confirm the live link works

After each step: run locally with `streamlit run app.py`, then commit and push so
Streamlit Cloud redeploys.

## Academic-integrity rules (important)
- The course allows GenAI to help write CODE. It prohibits AI-generated content for the
  submission itself: PRD, slides, analysis, user research, wireframes, mockups.
- So: help with code, debugging, git and deployment. Do NOT write the PRD, slide text,
  user personas, research findings, the README problem statement or the AI-use disclosure.
  Leave those sections as placeholders for the team to write.
- Explain code changes plainly — the team must be able to explain every line and every
  product decision in the presentation.
- Keep a short log of what you helped with so the team can write their AI-use disclosure.

## How to work with me
- Make the smallest change that completes the current step; ask before adding anything
  outside the MVP workflow above.
- Show `git status` before committing and pushing.
- When something fails, show the actual error, then fix it.
