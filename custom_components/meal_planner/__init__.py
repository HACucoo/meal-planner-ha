"""Meal Planner integration for Home Assistant."""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import json as _json
import random
import re

from aiohttp import web
from homeassistant.components.frontend import async_register_built_in_panel, async_remove_panel
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DEFAULT_DISHES,
    DOMAIN,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL,
    STORAGE_KEY,
    STORAGE_VERSION,
    TYPE_DISH,
)

_LOGGER = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Meal Planner from a config entry."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load()

    if data is None:
        data = _default_data()
        await store.async_save(data)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["store"] = store
    hass.data[DOMAIN]["data"] = data
    hass.data[DOMAIN]["rejected_sessions"] = {}

    # Serve static frontend files
    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}_frontend", str(FRONTEND_DIR), cache_headers=False)
    ])

    # Register API views
    hass.http.register_view(MealPlannerDishesView(hass))
    hass.http.register_view(MealPlannerDishView(hass))
    hass.http.register_view(MealPlannerPlanView(hass))
    hass.http.register_view(MealPlannerDayView(hass))
    hass.http.register_view(MealPlannerSuggestView(hass))
    hass.http.register_view(MealPlannerRejectView(hass))
    hass.http.register_view(MealPlannerUnblockView(hass))
    hass.http.register_view(MealPlannerHistoryCSVView(hass))
    hass.http.register_view(MealPlannerChefkochView(hass))

    # Register sidebar panel
    async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL,
        config={"url": f"/{DOMAIN}_frontend/index.html"},
        require_admin=False,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    async_remove_panel(hass, PANEL_URL)
    hass.data.pop(DOMAIN, None)
    return True


def _default_data() -> dict:
    today = date.today().isoformat()
    return {
        "dishes": [
            {
                "id": str(uuid.uuid4()),
                "name": name,
                "last_used": None,
                "blocked_until": None,
                "use_count": 0,
                "created_at": today,
            }
            for name in DEFAULT_DISHES
        ],
        "meal_plan": {},
    }


def _get_suggestions(data: dict, day_str: str, session_rejected_ids: list[str]) -> list[dict]:
    """Return up to 3 dish suggestions, prioritising least recently used.

    Excludes:
    - dishes blocked temporarily (blocked_until > today)
    - dishes skipped in the current session (session_rejected_ids)
    """
    today = date.today().isoformat()
    dishes = [
        d for d in data["dishes"]
        if d["id"] not in session_rejected_ids
        and (d.get("blocked_until") is None or d["blocked_until"] <= today)
    ]
    # Sort: never used first, then by last_used ascending
    dishes.sort(key=lambda d: (d["last_used"] is not None, d["last_used"] or ""))
    return dishes[:3]


# ---------------------------------------------------------------------------
# API Views
# ---------------------------------------------------------------------------

class MealPlannerDishesView(HomeAssistantView):
    """GET /api/meal_planner/dishes  – list all dishes.
    POST /api/meal_planner/dishes  – add a new dish."""

    url = "/api/meal_planner/dishes"
    name = "api:meal_planner:dishes"
    requires_auth = False  # local-only integration

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        data = self.hass.data[DOMAIN]["data"]
        return self.json(sorted(data["dishes"], key=lambda d: d["name"].lower()))

    async def post(self, request: web.Request) -> web.Response:
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            return self.json_message("name is required", status_code=400)

        data = self.hass.data[DOMAIN]["data"]
        # Avoid duplicates (case-insensitive)
        if any(d["name"].lower() == name.lower() for d in data["dishes"]):
            return self.json_message("dish already exists", status_code=409)

        dish = {
            "id": str(uuid.uuid4()),
            "name": name,
            "last_used": None,
            "blocked_until": None,
            "use_count": 0,
            "created_at": date.today().isoformat(),
        }
        data["dishes"].append(dish)
        await self.hass.data[DOMAIN]["store"].async_save(data)
        return self.json(dish, status_code=201)


class MealPlannerDishView(HomeAssistantView):
    """DELETE /api/meal_planner/dishes/{dish_id}  – remove a dish."""

    url = "/api/meal_planner/dishes/{dish_id}"
    name = "api:meal_planner:dish"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def delete(self, request: web.Request, dish_id: str) -> web.Response:
        data = self.hass.data[DOMAIN]["data"]
        before = len(data["dishes"])
        data["dishes"] = [d for d in data["dishes"] if d["id"] != dish_id]
        if len(data["dishes"]) == before:
            return self.json_message("not found", status_code=404)
        await self.hass.data[DOMAIN]["store"].async_save(data)
        return self.json_message("deleted")


class MealPlannerPlanView(HomeAssistantView):
    """GET /api/meal_planner/plan?week=YYYY-WNN  – return the full week plan."""

    url = "/api/meal_planner/plan"
    name = "api:meal_planner:plan"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        week_param = request.query.get("week")
        if week_param:
            try:
                year, week = week_param.split("-W")
                monday = datetime.strptime(f"{year}-W{week}-1", "%G-W%V-%u").date()
            except (ValueError, TypeError):
                return self.json_message("invalid week format, use YYYY-WNN", status_code=400)
        else:
            today = date.today()
            monday = today - timedelta(days=today.weekday())

        days = [monday + timedelta(days=i) for i in range(7)]
        data = self.hass.data[DOMAIN]["data"]
        result = {}
        for d in days:
            ds = d.isoformat()
            result[ds] = data["meal_plan"].get(ds)
        return self.json(result)


class MealPlannerDayView(HomeAssistantView):
    """POST /api/meal_planner/plan/{date}  – set or update a day's meal."""

    url = "/api/meal_planner/plan/{day}"
    name = "api:meal_planner:day"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request, day: str) -> web.Response:
        try:
            date.fromisoformat(day)
        except ValueError:
            return self.json_message("invalid date format", status_code=400)

        body = await request.json()
        plan_type = body.get("type")
        allowed_types = {"dish", "eating_out", "order", "nothing", "custom"}
        if plan_type not in allowed_types:
            return self.json_message(f"type must be one of {allowed_types}", status_code=400)

        data = self.hass.data[DOMAIN]["data"]
        entry: dict[str, Any] = {"type": plan_type}

        if plan_type == TYPE_DISH:
            dish_id = body.get("dish_id")
            dish = next((d for d in data["dishes"] if d["id"] == dish_id), None)
            if dish is None:
                return self.json_message("dish not found", status_code=404)
            dish["last_used"] = day
            dish["use_count"] = dish.get("use_count", 0) + 1
            entry["dish_id"] = dish_id
            entry["dish_name"] = dish["name"]
        elif plan_type == "custom":
            entry["dish_name"] = (body.get("dish_name") or "").strip()
            if not entry["dish_name"]:
                return self.json_message("dish_name is required for custom type", status_code=400)
            # Optionally add to dishes list
            if body.get("add_to_list"):
                if not any(d["name"].lower() == entry["dish_name"].lower() for d in data["dishes"]):
                    new_dish = {
                        "id": str(uuid.uuid4()),
                        "name": entry["dish_name"],
                        "last_used": day,
                        "blocked_until": None,
                        "use_count": 1,
                        "created_at": day,
                    }
                    data["dishes"].append(new_dish)
                    entry["dish_id"] = new_dish["id"]
        elif plan_type in ("eating_out", "order"):
            entry["dish_name"] = body.get("dish_name", "")
        elif plan_type == "nothing":
            entry["dish_name"] = ""

        data["meal_plan"][day] = entry
        # Clear rejection session for this day
        self.hass.data[DOMAIN]["rejected_sessions"].pop(day, None)
        await self.hass.data[DOMAIN]["store"].async_save(data)
        return self.json(entry, status_code=201)

    async def delete(self, request: web.Request, day: str) -> web.Response:
        data = self.hass.data[DOMAIN]["data"]
        data["meal_plan"].pop(day, None)
        self.hass.data[DOMAIN]["rejected_sessions"].pop(day, None)
        await self.hass.data[DOMAIN]["store"].async_save(data)
        return self.json_message("deleted")


class MealPlannerSuggestView(HomeAssistantView):
    """GET /api/meal_planner/suggest/{date}  – get 3 suggestions for a day."""

    url = "/api/meal_planner/suggest/{day}"
    name = "api:meal_planner:suggest"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, day: str) -> web.Response:
        data = self.hass.data[DOMAIN]["data"]
        rejected = self.hass.data[DOMAIN]["rejected_sessions"].get(day, [])
        suggestions = _get_suggestions(data, day, rejected)
        return self.json(suggestions)


class MealPlannerRejectView(HomeAssistantView):
    """POST /api/meal_planner/suggest/{date}/reject

    Body: { "dish_id": "...", "mode": "session" | "temporary" }

    - "session"   : skip only for this planning session (default)
    - "temporary" : block dish for 14 days (blocked_until = today + 14)
    """

    url = "/api/meal_planner/suggest/{day}/reject"
    name = "api:meal_planner:reject"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request, day: str) -> web.Response:
        body = await request.json()
        dish_id = body.get("dish_id")
        mode = body.get("mode", "session")  # "session" or "temporary"

        if not dish_id:
            return self.json_message("dish_id is required", status_code=400)
        if mode not in ("session", "temporary"):
            return self.json_message("mode must be 'session' or 'temporary'", status_code=400)

        data = self.hass.data[DOMAIN]["data"]
        sessions = self.hass.data[DOMAIN]["rejected_sessions"]

        if mode == "temporary":
            dish = next((d for d in data["dishes"] if d["id"] == dish_id), None)
            if dish is None:
                return self.json_message("dish not found", status_code=404)
            blocked_until = (date.today() + timedelta(days=14)).isoformat()
            dish["blocked_until"] = blocked_until
            await self.hass.data[DOMAIN]["store"].async_save(data)
            # Also add to session so it disappears immediately
            sessions.setdefault(day, [])
            if dish_id not in sessions[day]:
                sessions[day].append(dish_id)
        else:
            # Session-only: skip for today's planning, no persistent change
            sessions.setdefault(day, [])
            if dish_id not in sessions[day]:
                sessions[day].append(dish_id)

        suggestions = _get_suggestions(data, day, sessions[day])
        return self.json(suggestions)


class MealPlannerUnblockView(HomeAssistantView):
    """POST /api/meal_planner/dishes/{dish_id}/unblock  – clear a temporary block."""

    url = "/api/meal_planner/dishes/{dish_id}/unblock"
    name = "api:meal_planner:unblock"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request, dish_id: str) -> web.Response:
        data = self.hass.data[DOMAIN]["data"]
        dish = next((d for d in data["dishes"] if d["id"] == dish_id), None)
        if dish is None:
            return self.json_message("not found", status_code=404)
        dish["blocked_until"] = None
        await self.hass.data[DOMAIN]["store"].async_save(data)
        return self.json(dish)


class MealPlannerHistoryCSVView(HomeAssistantView):
    """GET /api/meal_planner/history.csv  – download full meal history as CSV."""

    url = "/api/meal_planner/history.csv"
    name = "api:meal_planner:history_csv"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        data = self.hass.data[DOMAIN]["data"]
        meal_plan = data.get("meal_plan", {})

        type_labels = {
            "dish": "Gekocht",
            "custom": "Gekocht",
            "eating_out": "Auswärts",
            "order": "Bestellt",
            "nothing": "Kein Kochen",
        }

        rows = ["Datum,Gericht,Typ"]
        for day_iso in sorted(meal_plan.keys()):
            entry = meal_plan[day_iso]
            dish_name = (entry.get("dish_name") or "").replace('"', '""')
            typ = type_labels.get(entry.get("type", ""), entry.get("type", ""))
            rows.append(f'{day_iso},"{dish_name}",{typ}')

        csv_content = "\n".join(rows) + "\n"
        return web.Response(
            body=csv_content.encode("utf-8-sig"),  # utf-8-sig for Excel compatibility
            content_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=meal-history.csv"},
        )


class MealPlannerChefkochView(HomeAssistantView):
    """GET /api/meal_planner/surprise/chefkoch  – random recipe via Chefkoch JSON API."""

    url = "/api/meal_planner/surprise/chefkoch"
    name = "api:meal_planner:surprise_chefkoch"
    requires_auth = False

    # Rotating search terms for variety
    _QUERIES = [
        "Abendessen", "Pasta", "Suppe", "Auflauf", "Pfanne",
        "Salat", "Eintopf", "Ofengericht", "Curry", "Fleisch",
        "vegetarisch", "Fisch", "Hähnchen", "Rind", "Gemüse",
    ]

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Accept-Language": "de-DE,de;q=0.9",
        "Referer": "https://www.chefkoch.de/",
    }

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        session = async_get_clientsession(self.hass)
        query = random.choice(self._QUERIES)

        # Step 1: get total count for this query with a minimal request
        api_url = "https://api.chefkoch.de/v2/recipes"
        params = {"query": query, "limit": 1, "offset": 0}
        try:
            async with session.get(
                api_url, params=params, headers=self._HEADERS, timeout=10
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning("Chefkoch API status %s for query '%s'", resp.status, query)
                    return self.json_message("chefkoch api error", status_code=502)
                data = await resp.json(content_type=None)
        except Exception as exc:
            _LOGGER.warning("Chefkoch API fetch failed: %s", exc)
            return self.json_message("chefkoch unreachable", status_code=502)

        total = data.get("count", 0)
        if not total:
            _LOGGER.warning("Chefkoch: no results for query '%s'", query)
            return self.json_message("no recipes found", status_code=404)

        # Step 2: pick a random recipe within the first 200 results
        offset = random.randint(0, min(total - 1, 199))
        params = {"query": query, "limit": 1, "offset": offset}
        try:
            async with session.get(
                api_url, params=params, headers=self._HEADERS, timeout=10
            ) as resp:
                data = await resp.json(content_type=None)
        except Exception as exc:
            _LOGGER.warning("Chefkoch API fetch (offset) failed: %s", exc)
            return self.json_message("chefkoch unreachable", status_code=502)

        results = data.get("results") or []
        if not results:
            return self.json_message("no recipes found", status_code=404)

        meal = results[0]
        title = meal.get("title") or meal.get("name") or ""
        site_url = meal.get("siteUrl") or ""

        # Image: template has {size} and {formatId} placeholders
        img_template = meal.get("previewImageUrlTemplate") or meal.get("previewImageUrl") or ""
        image = (
            img_template.replace("{size}", "400x300").replace("{formatId}", "1")
            if img_template else None
        )

        return self.json({
            "name": title,
            "image": image,
            "url": site_url,
            "source": "Chefkoch",
        })
