# AI assistance log (code only)

Raw notes for the team to use when writing the AI-use disclosure. This is not the disclosure itself.

| Date | Tool | What it helped with |
|---|---|---|
| 2026-11-11 | Claude Code | Step 2: wrote `planner.py` (prompt built from the brief and places.json, JSON-mode Gemini call, safe parsing, dropping ids that aren't in places.json). Replaced the Step 1 data listing in `app.py` with the trip brief form, itinerary generation and day cards. Wrote throwaway offline tests with a fake Gemini client. Found and fixed a bug where the form key clashed with a `session_state` key. |
