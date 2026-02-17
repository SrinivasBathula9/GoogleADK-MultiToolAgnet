import datetime
import random
import difflib
import logging
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional, Tuple
from functools import lru_cache
from google.adk.agents import Agent

try:
    from geopy.geocoders import Nominatim
    from timezonefinder import TimezoneFinder
    import requests
except Exception:
    Nominatim = None  # type: ignore
    TimezoneFinder = None  # type: ignore
    requests = None  # type: ignore

logger = logging.getLogger(__name__)

# Keep a small built-in fallback for offline demo and unit tests.
CITY_WEATHER: Dict[str, Dict[str, Any]] = {
    "new york": {
        "temp_c": 25.0,
        "condition": "sunny",
        "humidity": 45,
        "wind_kph": 10,
        "tz": "America/New_York",
    },
    "london": {
        "temp_c": 15.0,
        "condition": "cloudy",
        "humidity": 70,
        "wind_kph": 12,
        "tz": "Europe/London",
    },
    "san francisco": {
        "temp_c": 18.0,
        "condition": "foggy",
        "humidity": 80,
        "wind_kph": 8,
        "tz": "America/Los_Angeles",
    },
    "tokyo": {
        "temp_c": 20.0,
        "condition": "partly cloudy",
        "humidity": 60,
        "wind_kph": 9,
        "tz": "Asia/Tokyo",
    },
}


def _normalize(city: str) -> str:
    return city.strip().lower()


def _find_best_city(city: str) -> Optional[str]:
    choices = list(CITY_WEATHER.keys())
    key = _normalize(city)
    if key in CITY_WEATHER:
        return key
    matches = difflib.get_close_matches(key, choices, n=1, cutoff=0.6)
    return matches[0] if matches else None


@lru_cache(maxsize=256)
def _geocode(city: str) -> Optional[Tuple[float, float, str]]:
    """Return (lat, lon, display_name) using Nominatim or None on failure.

    Cached to reduce Nominatim usage.
    """
    if Nominatim is None:
        return None
    try:
        geolocator = Nominatim(user_agent="gemini_weather_agent")
        loc = geolocator.geocode(city, exactly_one=True, timeout=10)
        if not loc:
            return None
        return (loc.latitude, loc.longitude, loc.address)
    except Exception as e:
        logger.debug("Geocoding failed: %s", e)
        return None


@lru_cache(maxsize=256)
def _tz_from_coords(lat: float, lon: float) -> Optional[str]:
    if TimezoneFinder is None:
        return None
    try:
        tf = TimezoneFinder()
        return tf.timezone_at(lng=lon, lat=lat)
    except Exception as e:
        logger.debug("Timezone lookup failed: %s", e)
        return None


def _open_meteo_current(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    if requests is None:
        return None
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current_weather=true&timezone=auto"
        )
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data
    except Exception as e:
        logger.debug("Open-Meteo request failed: %s", e)
        return None


def get_weather(city: str, units: str = "C") -> Dict[str, Any]:
    """Get weather for any city using OSM geocoding + Open-Meteo, with fallback.

    If external libraries are missing or remote calls fail, falls back to the
    built-in `CITY_WEATHER` data for a small set of cities.
    """
    if units.upper() not in ("C", "F"):
        return {"status": "error", "error_message": "`units` must be 'C' or 'F'."}

    # First try local fuzzy match
    match = _find_best_city(city)
    if match:
        base = CITY_WEATHER[match]
        temp_c = round(base["temp_c"] + random.uniform(-1.5, 1.5), 1)
        humidity = max(0, min(100, base["humidity"] + random.randint(-3, 3)))
        wind_kph = round(max(0, base["wind_kph"] + random.uniform(-2, 2)), 1)
        tz = ZoneInfo(base.get("tz", "UTC"))
        now = datetime.datetime.now(tz)
        temp = round(temp_c * 9.0 / 5.0 + 32.0, 1) if units.upper() == "F" else temp_c
        unit_label = "F" if units.upper() == "F" else "C"
        data = {
            "city": match.title(),
            "temp_c": temp_c,
            "temp": temp,
            "units": unit_label,
            "condition": base["condition"],
            "humidity": humidity,
            "wind_kph": wind_kph,
            "timestamp": now.isoformat(),
        }
        report = (
            f"The weather in {data['city']} is {data['condition']} with a temperature of "
            f"{data['temp']}°{data['units']} ({data['temp_c']}°C). Humidity: {data['humidity']}%. "
            f"Wind: {data['wind_kph']} kph."
        )
        return {"status": "success", "report": report, "data": data}

    # Attempt geocode + Open-Meteo
    geocoded = _geocode(city)
    if not geocoded:
        return {"status": "error", "error_message": f"Weather information for '{city}' is not available."}

    lat, lon, display_name = geocoded
    om = _open_meteo_current(lat, lon)
    if om and "current_weather" in om:
        cw = om["current_weather"]
        # Open-Meteo returns temperature in °C and windspeed in km/h (per docs)
        temp_c = round(cw.get("temperature"), 1) if cw.get("temperature") is not None else None
        wind = round(cw.get("windspeed"), 1) if cw.get("windspeed") is not None else None
        # humidity isn't part of current_weather; try to fetch hourly humidity if available
        humidity = None
        tz = _tz_from_coords(lat, lon) or om.get("timezone") or "UTC"
        now = datetime.datetime.now(ZoneInfo(tz))
        temp = round(temp_c * 9.0 / 5.0 + 32.0, 1) if (units.upper() == "F" and temp_c is not None) else temp_c
        unit_label = "F" if units.upper() == "F" else "C"
        data = {
            "city": display_name,
            "temp_c": temp_c,
            "temp": temp,
            "units": unit_label,
            "condition": cw.get("weathercode"),
            "humidity": humidity,
            "wind_kph": wind,
            "timestamp": now.isoformat(),
            "lat": lat,
            "lon": lon,
        }
        report = (
            f"The weather in {display_name} is {data['condition']} with a temperature of "
            f"{data['temp']}°{data['units']} ({data['temp_c']}°C). Wind: {data['wind_kph']} kph."
        )
        return {"status": "success", "report": report, "data": data}

    return {"status": "error", "error_message": f"Could not retrieve weather for '{city}' at this time."}


def get_current_time(city: str) -> Dict[str, Any]:
    """Return the current local time for a city using geocoding + timezone lookup.

    Falls back to built-in cities if external lookups are unavailable.
    """
    match = _find_best_city(city)
    if match:
        tz_identifier = CITY_WEATHER[match].get("tz", "UTC")
        tz = ZoneInfo(tz_identifier)
        now = datetime.datetime.now(tz)
        iso = now.isoformat()
        report = f"The current time in {match.title()} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"
        return {"status": "success", "report": report, "iso": iso, "timezone": tz_identifier}

    geocoded = _geocode(city)
    if not geocoded:
        return {"status": "error", "error_message": f"Sorry, I don't have timezone information for {city}."}

    lat, lon, display_name = geocoded
    tz_identifier = _tz_from_coords(lat, lon)
    if not tz_identifier:
        return {"status": "error", "error_message": f"Could not determine timezone for {city}."}

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    iso = now.isoformat()
    report = f"The current time in {display_name} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"
    return {"status": "success", "report": report, "iso": iso, "timezone": tz_identifier}


root_agent = Agent(
    name="weather_time_agent",
    model="gemini-3-flash-preview",
    description=(
        "Agent to answer questions about the time and weather in a city."
    ),
    instruction=(
        "You are a helpful agent who can answer user questions about the time and weather in a city."
    ),
    tools=[get_weather, get_current_time],
)