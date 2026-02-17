# GoogleADK-MultiToolAgent

**Project:** Multi-tool agent built on Google ADK that provides time and weather information for cities worldwide using open-source services when possible.

**Status:** Prototype — local fallbacks + optional OpenStreetMap/Open-Meteo integration.

**Highlights**
- **No required API keys** by default — uses `geopy` (Nominatim) + `timezonefinder` + Open-Meteo (no-key) when available.
- **Fallback data** for offline/demo use (small set of built-in cities).
- **Structured responses**: functions return `status`, `data`, and human-friendly `report` strings.
- **Fuzzy matching** for common city name typos.

**Quick Start**
- Install dependencies:

```bash
pip install -r requirements.txt
```

- Run a quick test (examples provided in `multi_agents/agent.py`):

```bash
python - <<'PY'
from multi_agents import agent
print(agent.get_weather("New York"))
print(agent.get_current_time("Tokyo"))
PY
```

**Folder Structure**
- `main.py`: optional runner/entry point.
- `requirements.txt`: Python dependencies.
- `pyproject.toml`: project metadata.
- `multi_agents/`:
	- `__init__.py`
	- `agent.py` — main agent code: `get_weather`, `get_current_time`, integration helpers.

**Google ADK Integration**
- The project constructs a `root_agent` using `google.adk.agents.Agent` in `multi_agents/agent.py`.
- `root_agent` exposes two tool callables to the ADK runtime:
	- `get_weather(city, units='C')` — returns structured weather data and a readable report.
	- `get_current_time(city)` — returns local time, ISO timestamp, and timezone.
- The `Agent` is configured with `name`, `model`, `description`, and `instruction` fields (see `multi_agents/agent.py`).

**Implementation Notes & Caveats**
- Nominatim (OpenStreetMap) and Open-Meteo are free but have rate limits and usage policies. Cache geocoding results and avoid abusive usage.
- If `geopy`, `timezonefinder`, or `requests` are not installed or network calls fail, the agent falls back to built-in sample data for demonstration.
- `.env` is added to `.gitignore`; put any secret keys there if you extend the project to use paid APIs.

**Next Steps (suggested)**
- Add caching layer (Redis or disk) for geocoding results.
- Add unit tests and GitHub Actions CI.
- Optionally add support for paid providers (OpenWeatherMap, Google Time Zone) behind feature flags and environment variables.

---
Created and maintained in this repository. For usage questions, open an issue.

**Execution Results**

Screenshot of an example execution/results screen:

![Execution Results - UI](multi_agents/UI%20.png)

## Web demo & Metrics

- A FastAPI demo (`web/app.py`) exposes:
	- `/` — simple UI to query weather and time.
	- `/api/weather` — POST endpoint (form) returning JSON from `get_weather`.
	- `/api/time` — POST endpoint (form) returning JSON from `get_current_time`.
	- `/metrics` — Prometheus metrics (request counts and latency).

Run locally:

```bash
pip install -r requirements.txt
& "D:/ML/Agentic AI/Gemini/.venv/Scripts/python.exe" -m uvicorn web.app:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000` to try the demo and `http://127.0.0.1:8000/metrics` to view metrics.

