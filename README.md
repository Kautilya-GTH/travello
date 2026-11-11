# Travello

<!-- Write this section yourselves: one or two lines on the problem and who it's for. -->

**Live app:** _add Streamlit Cloud link_

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then add your key
streamlit run app.py
```

## Project structure

| Path | Purpose |
|---|---|
| `app.py` | Streamlit app |
| `planner.py` | Gemini prompts, JSON parsing, place-id validation |
| `data/places.json` | Curated places, food and stays for Goa, Jaipur, Kyoto, Bali |
| `requirements.txt` | Python dependencies |

## AI use disclosure

<!-- Required by the course. Write this yourselves: which AI tools you used, and for what. -->

## Team

<!-- Group number and members -->
