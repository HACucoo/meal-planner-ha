"""Meal Planner integration for Home Assistant."""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
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
    hass.http.register_static_path(
        f"/{DOMAIN}_frontend",
        str(FRONTEND_DIR),
        cache_headers=False,
    )

    # Register API views
    hass.http.register_view(MealPlannerDishesView(hass))
    hass.http.register_view(MealPlannerDishView(hass))
    hass.http.register_view(MealPlannerPlanView(hass))
    hass.http.register_view(MealPlannerDayView(hass))
    hass.http.register_view(MealPlannerSuggestView(hass))
    hass.http.register_view(MealPlannerRejectView(hass))
    hass.http.register_view(MealPlannerUnblockView(hass))

    # Register sidebar panel
    hass.components.frontend.async_register_built_in_panel(
        "iframe",
        PANEL_TITLE,
        PANEL_ICON,
        PANEL_URL,
        {"url": f"/{DOMAIN}_frontend/index.html"},
        require_admin=False,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.components.frontend.async_remove_panel(PANEL_URL)
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
                monday = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w").date()
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
