"""Meal Planner integration for Home Assistant."""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import random

from aiohttp import web
from homeassistant.components.frontend import async_register_built_in_panel, async_remove_panel
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store

from .const import (
    DEFAULT_DISHES,
    DOMAIN,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL,
    STORAGE_KEY,
    STORAGE_VERSION,
    TYPE_CUSTOM,
    TYPE_DISH,
    TYPE_EATING_OUT,
    TYPE_NOTHING,
    TYPE_ORDER,
)

_LOGGER = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"

# HTTP routes can only be registered once per HA run — survives entry reloads
DATA_HTTP_REGISTERED = f"{DOMAIN}_http_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Meal Planner from a config entry."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load()

    if data is None:
        data = _default_data()
        await store.async_save(data)

    # Usage counters are derived from the plan — heals any drift from older versions
    _recompute_dish_usage(data)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["store"] = store
    hass.data[DOMAIN]["data"] = data
    hass.data[DOMAIN]["rejected_sessions"] = {}
    hass.data[DOMAIN]["entry"] = entry

    # Static files + API views — register once per HA run (reload-safe)
    if not hass.data.get(DATA_HTTP_REGISTERED):
        await hass.http.async_register_static_paths([
            StaticPathConfig(f"/{DOMAIN}_frontend", str(FRONTEND_DIR), cache_headers=False)
        ])
        for view_cls in (
            MealPlannerDishesView,
            MealPlannerDishView,
            MealPlannerPlanView,
            MealPlannerDayView,
            MealPlannerMoveView,
            MealPlannerSuggestView,
            MealPlannerRejectView,
            MealPlannerUnblockView,
            MealPlannerHistoryCSVView,
            MealPlannerChefkochView,
            MealPlannerSettingsView,
            MealPlannerStatsView,
            MealPlannerHolidaysView,
        ):
            hass.http.register_view(view_cls(hass))
        hass.data[DATA_HTTP_REGISTERED] = True

    # Set up sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    # At midnight the just-arrived day starts counting towards dish usage
    async def _midnight_refresh(_now: datetime) -> None:
        _recompute_dish_usage(data)
        _cleanup_rejected_sessions(hass)
        await store.async_save(data)
        _push_sensor_update(hass)

    hass.data[DOMAIN]["cancel_midnight"] = async_track_time_change(
        hass, _midnight_refresh, hour=0, minute=0, second=30
    )

    # Apply option changes (language, holiday country/state) without an HA restart
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

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
    if cancel := hass.data.get(DOMAIN, {}).get("cancel_midnight"):
        cancel()
    await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    async_remove_panel(hass, PANEL_URL)
    hass.data.pop(DOMAIN, None)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options change so they apply immediately."""
    await hass.config_entries.async_reload(entry.entry_id)


def _push_sensor_update(hass: HomeAssistant) -> None:
    """Trigger a state refresh on all meal plan sensors."""
    for sensor in hass.data.get(DOMAIN, {}).get("sensors", []):
        sensor.async_write_ha_state()


def _recompute_dish_usage(data: dict, today_iso: str | None = None) -> None:
    """Derive use_count / last_used for every dish from the meal plan.

    The plan is the single source of truth, so usage stays exact no matter how
    entries are added, edited, moved, swapped or deleted. Days planned for the
    future don't count until they arrive (the midnight job re-runs this).
    Entries without a dish_id are matched by name, so a deleted and re-added
    dish regains its history.
    """
    if today_iso is None:
        today_iso = date.today().isoformat()
    dishes = data.get("dishes", [])
    by_id = {d["id"]: d for d in dishes}
    by_name = {d["name"].lower(): d for d in dishes}
    for d in dishes:
        d["use_count"] = 0
        d["last_used"] = None
    for day_iso, plan_entry in data.get("meal_plan", {}).items():
        if day_iso > today_iso or plan_entry.get("type") not in (TYPE_DISH, TYPE_CUSTOM):
            continue
        dish = by_id.get(plan_entry.get("dish_id")) or by_name.get(
            (plan_entry.get("dish_name") or "").strip().lower()
        )
        if dish is None:
            continue
        dish["use_count"] += 1
        if not dish["last_used"] or dish["last_used"] < day_iso:
            dish["last_used"] = day_iso


def _cleanup_rejected_sessions(hass: HomeAssistant) -> None:
    """Remove stale rejection sessions for past dates."""
    sessions = hass.data.get(DOMAIN, {}).get("rejected_sessions")
    if not sessions:
        return
    today_iso = date.today().isoformat()
    stale = [k for k in sessions if k < today_iso]
    for k in stale:
        del sessions[k]


def _new_dish(name: str) -> dict:
    """Create a fresh dish record."""
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "last_used": None,
        "blocked_until": None,
        "use_count": 0,
        "created_at": date.today().isoformat(),
    }


def _default_data() -> dict:
    return {
        "dishes": [_new_dish(name) for name in DEFAULT_DISHES],
        "meal_plan": {},
    }


def _get_suggestions(data: dict, day_str: str, session_rejected_ids: list[str]) -> list[dict]:
    """Return up to 3 dish suggestions, prioritising least recently used.

    Excludes:
    - dishes still blocked on the day being planned (a block that expires
      before a future target day no longer hides the dish for that day)
    - dishes skipped in the current session (session_rejected_ids)
    """
    effective_day = max(date.today().isoformat(), day_str or "")
    dishes = [
        d for d in data["dishes"]
        if d["id"] not in session_rejected_ids
        and (d.get("blocked_until") is None or d["blocked_until"] <= effective_day)
    ]
    # Sort: never used first, then by last_used ascending
    dishes.sort(key=lambda d: (d["last_used"] is not None, d["last_used"] or ""))
    # Pick randomly from the oldest-used candidates for variety
    pool = dishes[:max(3, min(10, len(dishes)))]
    random.shuffle(pool)
    return pool[:3]


# ---------------------------------------------------------------------------
# API Views
# ---------------------------------------------------------------------------

class MealPlannerBaseView(HomeAssistantView):
    """Shared plumbing for the Meal Planner API views.

    requires_auth is False on purpose: the sidebar panel is an iframe whose
    fetch() calls carry no HA auth token. The API is intended for trusted
    local networks only.
    """

    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    @staticmethod
    async def read_json(request: web.Request) -> dict | None:
        """Return the request body as a dict, or None if it isn't valid JSON."""
        try:
            body = await request.json()
        except ValueError:
            return None
        return body if isinstance(body, dict) else None


class MealPlannerDishesView(MealPlannerBaseView):
    """GET /api/meal_planner/dishes  – list all dishes.
    POST /api/meal_planner/dishes  – add a new dish."""

    url = "/api/meal_planner/dishes"
    name = "api:meal_planner:dishes"

    async def get(self, request: web.Request) -> web.Response:
        data = self.hass.data[DOMAIN]["data"]
        return self.json(sorted(data["dishes"], key=lambda d: d["name"].lower()))

    async def post(self, request: web.Request) -> web.Response:
        body = await self.read_json(request)
        if body is None:
            return self.json_message("invalid JSON body", status_code=400)
        name = (body.get("name") or "").strip()
        if not name:
            return self.json_message("name is required", status_code=400)
        if len(name) > 200:
            return self.json_message("name too long (max 200 characters)", status_code=400)

        data = self.hass.data[DOMAIN]["data"]
        # Avoid duplicates (case-insensitive)
        if any(d["name"].lower() == name.lower() for d in data["dishes"]):
            return self.json_message("dish already exists", status_code=409)

        dish = _new_dish(name)
        data["dishes"].append(dish)
        # A re-added dish regains its history from matching plan entries
        _recompute_dish_usage(data)
        await self.hass.data[DOMAIN]["store"].async_save(data)
        return self.json(dish, status_code=201)


class MealPlannerDishView(MealPlannerBaseView):
    """DELETE /api/meal_planner/dishes/{dish_id}  – remove a dish."""

    url = "/api/meal_planner/dishes/{dish_id}"
    name = "api:meal_planner:dish"

    async def delete(self, request: web.Request, dish_id: str) -> web.Response:
        data = self.hass.data[DOMAIN]["data"]
        before = len(data["dishes"])
        data["dishes"] = [d for d in data["dishes"] if d["id"] != dish_id]
        if len(data["dishes"]) == before:
            return self.json_message("not found", status_code=404)
        await self.hass.data[DOMAIN]["store"].async_save(data)
        return self.json_message("deleted")


class MealPlannerPlanView(MealPlannerBaseView):
    """GET /api/meal_planner/plan?week=YYYY-WNN  – return the full week plan."""

    url = "/api/meal_planner/plan"
    name = "api:meal_planner:plan"

    async def get(self, request: web.Request) -> web.Response:
        from_param = request.query.get("from")
        to_param = request.query.get("to")
        week_param = request.query.get("week")

        if from_param and to_param:
            try:
                start = date.fromisoformat(from_param)
                end = date.fromisoformat(to_param)
            except ValueError:
                return self.json_message("invalid date format, use YYYY-MM-DD", status_code=400)
            span = (end - start).days
            if span < 0 or span > 366:
                return self.json_message("date range must be 0–366 days", status_code=400)
            days = [start + timedelta(days=i) for i in range(span + 1)]
        elif week_param:
            try:
                year, week = week_param.split("-W")
                monday = datetime.strptime(f"{year}-W{week}-1", "%G-W%V-%u").date()
            except (ValueError, TypeError):
                return self.json_message("invalid week format, use YYYY-WNN", status_code=400)
            days = [monday + timedelta(days=i) for i in range(7)]
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


class MealPlannerDayView(MealPlannerBaseView):
    """POST /api/meal_planner/plan/{date}  – set or update a day's meal."""

    url = "/api/meal_planner/plan/{day}"
    name = "api:meal_planner:day"

    async def post(self, request: web.Request, day: str) -> web.Response:
        try:
            date.fromisoformat(day)
        except ValueError:
            return self.json_message("invalid date format", status_code=400)

        body = await self.read_json(request)
        if body is None:
            return self.json_message("invalid JSON body", status_code=400)
        plan_type = body.get("type")
        allowed_types = {TYPE_DISH, TYPE_EATING_OUT, TYPE_ORDER, TYPE_NOTHING, TYPE_CUSTOM}
        if plan_type not in allowed_types:
            return self.json_message(f"type must be one of {allowed_types}", status_code=400)

        data = self.hass.data[DOMAIN]["data"]
        entry: dict[str, Any] = {"type": plan_type}
        dish_name = (body.get("dish_name") or "").strip()
        if len(dish_name) > 200:
            return self.json_message("dish_name too long (max 200 characters)", status_code=400)

        if plan_type == TYPE_DISH:
            dish = next((d for d in data["dishes"] if d["id"] == body.get("dish_id")), None)
            if dish is None:
                return self.json_message("dish not found", status_code=404)
            entry["dish_id"] = dish["id"]
            entry["dish_name"] = dish["name"]
        elif plan_type == TYPE_CUSTOM:
            if not dish_name:
                return self.json_message("dish_name is required for custom type", status_code=400)
            entry["dish_name"] = dish_name
            # Optionally add to the dish list
            if body.get("add_to_list") and not any(
                d["name"].lower() == dish_name.lower() for d in data["dishes"]
            ):
                data["dishes"].append(_new_dish(dish_name))
            # Link the entry to a matching dish so usage tracking finds it
            match = next(
                (d for d in data["dishes"] if d["name"].lower() == dish_name.lower()), None
            )
            if match:
                entry["dish_id"] = match["id"]
        elif plan_type in (TYPE_EATING_OUT, TYPE_ORDER):
            entry["dish_name"] = dish_name
        elif plan_type == TYPE_NOTHING:
            entry["dish_name"] = ""

        data["meal_plan"][day] = entry
        _recompute_dish_usage(data)
        # Clear rejection session for this day
        self.hass.data[DOMAIN]["rejected_sessions"].pop(day, None)
        await self.hass.data[DOMAIN]["store"].async_save(data)
        _push_sensor_update(self.hass)
        return self.json(entry, status_code=201)

    async def delete(self, request: web.Request, day: str) -> web.Response:
        data = self.hass.data[DOMAIN]["data"]
        data["meal_plan"].pop(day, None)
        _recompute_dish_usage(data)
        self.hass.data[DOMAIN]["rejected_sessions"].pop(day, None)
        await self.hass.data[DOMAIN]["store"].async_save(data)
        _push_sensor_update(self.hass)
        return self.json_message("deleted")


class MealPlannerMoveView(MealPlannerBaseView):
    """POST /api/meal_planner/plan/{day}/move  – move or swap a day's meal.

    Body: { "target": "YYYY-MM-DD" }

    - If the target day is empty, the source entry is moved there and the
      source day is cleared.
    - If the target day already has an entry, the two entries are swapped.

    Usage counters are recomputed from the plan afterwards, so moves across
    the today boundary are reflected immediately.
    """

    url = "/api/meal_planner/plan/{day}/move"
    name = "api:meal_planner:move"

    async def post(self, request: web.Request, day: str) -> web.Response:
        try:
            date.fromisoformat(day)
        except ValueError:
            return self.json_message("invalid date format", status_code=400)

        body = await self.read_json(request)
        if body is None:
            return self.json_message("invalid JSON body", status_code=400)
        target = body.get("target")
        try:
            date.fromisoformat(target)
        except (ValueError, TypeError):
            return self.json_message("invalid or missing target date", status_code=400)

        if target == day:
            return self.json_message("target must differ from source", status_code=400)

        data = self.hass.data[DOMAIN]["data"]
        meal_plan = data.setdefault("meal_plan", {})

        src_entry = meal_plan.get(day)
        if src_entry is None:
            return self.json_message("nothing planned on source day", status_code=404)

        dst_entry = meal_plan.get(target)
        if dst_entry is None:
            # Move: relocate to target, clear source
            meal_plan[target] = src_entry
            meal_plan.pop(day, None)
        else:
            # Swap the two days' entries
            meal_plan[day] = dst_entry
            meal_plan[target] = src_entry

        _recompute_dish_usage(data)

        # Rejection sessions are per-day planning aids — drop them for both days
        sessions = self.hass.data[DOMAIN]["rejected_sessions"]
        sessions.pop(day, None)
        sessions.pop(target, None)

        await self.hass.data[DOMAIN]["store"].async_save(data)
        _push_sensor_update(self.hass)
        return self.json({
            "source": {"date": day, "entry": meal_plan.get(day)},
            "target": {"date": target, "entry": meal_plan.get(target)},
        })


class MealPlannerSuggestView(MealPlannerBaseView):
    """GET /api/meal_planner/suggest/{date}  – get 3 suggestions for a day."""

    url = "/api/meal_planner/suggest/{day}"
    name = "api:meal_planner:suggest"

    async def get(self, request: web.Request, day: str) -> web.Response:
        data = self.hass.data[DOMAIN]["data"]
        rejected = self.hass.data[DOMAIN]["rejected_sessions"].get(day, [])
        suggestions = _get_suggestions(data, day, rejected)
        return self.json(suggestions)


class MealPlannerRejectView(MealPlannerBaseView):
    """POST /api/meal_planner/suggest/{date}/reject

    Body: { "dish_id": "...", "mode": "session" | "temporary" }

    - "session"   : skip only for this planning session (default)
    - "temporary" : block dish for 14 days (blocked_until = today + 14)
    """

    url = "/api/meal_planner/suggest/{day}/reject"
    name = "api:meal_planner:reject"

    async def post(self, request: web.Request, day: str) -> web.Response:
        body = await self.read_json(request)
        if body is None:
            return self.json_message("invalid JSON body", status_code=400)
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


class MealPlannerUnblockView(MealPlannerBaseView):
    """POST /api/meal_planner/dishes/{dish_id}/unblock  – clear a temporary block."""

    url = "/api/meal_planner/dishes/{dish_id}/unblock"
    name = "api:meal_planner:unblock"

    async def post(self, request: web.Request, dish_id: str) -> web.Response:
        data = self.hass.data[DOMAIN]["data"]
        dish = next((d for d in data["dishes"] if d["id"] == dish_id), None)
        if dish is None:
            return self.json_message("not found", status_code=404)
        dish["blocked_until"] = None
        await self.hass.data[DOMAIN]["store"].async_save(data)
        return self.json(dish)


class MealPlannerHistoryCSVView(MealPlannerBaseView):
    """GET /api/meal_planner/history.csv  – download full meal history as CSV."""

    url = "/api/meal_planner/history.csv"
    name = "api:meal_planner:history_csv"

    _TYPE_LABELS: dict[str, dict[str, str]] = {
        "de": {
            "dish": "Gekocht", "custom": "Gekocht",
            "eating_out": "Auswärts", "order": "Bestellt", "nothing": "Kein Kochen",
        },
        "en": {
            "dish": "Cooked", "custom": "Cooked",
            "eating_out": "Eating out", "order": "Ordered", "nothing": "No cooking",
        },
    }
    _CSV_HEADERS: dict[str, str] = {
        "de": "Datum,Gericht,Typ",
        "en": "Date,Dish,Type",
    }

    async def get(self, request: web.Request) -> web.Response:
        config_entry = self.hass.data.get(DOMAIN, {}).get("entry")
        lang = config_entry.options.get("lang", "de") if config_entry else "de"
        type_labels = self._TYPE_LABELS.get(lang, self._TYPE_LABELS["de"])

        data = self.hass.data[DOMAIN]["data"]
        meal_plan = data.get("meal_plan", {})

        rows = [self._CSV_HEADERS[lang]]
        for day_iso in sorted(meal_plan.keys()):
            plan_entry = meal_plan[day_iso]
            dish_name = (plan_entry.get("dish_name") or "").replace('"', '""')
            # Guard against spreadsheet formula injection (leading =, +, -, @)
            if dish_name[:1] in ("=", "+", "-", "@"):
                dish_name = "'" + dish_name
            typ = type_labels.get(plan_entry.get("type", ""), plan_entry.get("type", ""))
            rows.append(f'{day_iso},"{dish_name}",{typ}')

        csv_content = "\n".join(rows) + "\n"
        return web.Response(
            body=csv_content.encode("utf-8-sig"),  # utf-8-sig for Excel compatibility
            content_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=meal-history.csv"},
        )


class MealPlannerChefkochView(MealPlannerBaseView):
    """GET /api/meal_planner/surprise/chefkoch  – random recipe via Chefkoch JSON API."""

    url = "/api/meal_planner/surprise/chefkoch"
    name = "api:meal_planner:surprise_chefkoch"

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
                if resp.status != 200:
                    _LOGGER.warning("Chefkoch API status %s on offset fetch", resp.status)
                    return self.json_message("chefkoch api error", status_code=502)
                data = await resp.json(content_type=None)
        except Exception as exc:
            _LOGGER.warning("Chefkoch API fetch (offset) failed: %s", exc)
            return self.json_message("chefkoch unreachable", status_code=502)

        results = data.get("results") or []
        if not results:
            return self.json_message("no recipes found", status_code=404)

        raw = results[0]
        # API may return the recipe directly or nested under a "recipe" key
        meal = raw.get("recipe") or raw

        title = (
            meal.get("title")
            or meal.get("name")
            or meal.get("headline")
            or ""
        )
        site_url = meal.get("siteUrl") or meal.get("url") or ""

        # Image: template URL carries a <format> placeholder
        img_template = meal.get("previewImageUrlTemplate") or meal.get("previewImageUrl") or ""
        _LOGGER.debug("Chefkoch image template: %s", img_template)
        image = (
            img_template.replace("<format>", "crop-960x540")
            if img_template else None
        )

        if not title:
            _LOGGER.warning(
                "Chefkoch: could not extract title. Available keys: %s",
                list(meal.keys()),
            )
            return self.json_message("no recipe title found", status_code=404)

        return self.json({
            "name": title,
            "image": image,
            "url": site_url,
            "source": "Chefkoch",
        })


class MealPlannerSettingsView(MealPlannerBaseView):
    """Return integration options (e.g. language) to the frontend."""

    url = "/api/meal_planner/settings"
    name = "api:meal_planner:settings"

    async def get(self, request: web.Request) -> web.Response:
        entry: ConfigEntry = self.hass.data.get(DOMAIN, {}).get("entry")
        lang = entry.options.get("lang", "de") if entry else "de"
        return self.json({"lang": lang})


class MealPlannerStatsView(MealPlannerBaseView):
    """GET /api/meal_planner/stats – aggregated cooking statistics."""

    url = "/api/meal_planner/stats"
    name = "api:meal_planner:stats"

    async def get(self, request: web.Request) -> web.Response:
        data = self.hass.data[DOMAIN]["data"]
        meal_plan = data.get("meal_plan", {})

        dish_counts: dict[str, int] = {}
        out_counts: dict[str, int] = {}
        order_counts: dict[str, int] = {}
        total_cooked = 0
        total_out = 0
        total_order = 0
        total_nothing = 0
        total_days = 0

        today_iso = date.today().isoformat()
        # Statistics reflect what has actually been cooked — skip future-planned days
        for day_iso, entry in meal_plan.items():
            if day_iso > today_iso:
                continue
            total_days += 1
            t = entry.get("type", "")
            name = (entry.get("dish_name") or "").strip()
            if t in ("dish", "custom"):
                total_cooked += 1
                if name:
                    dish_counts[name] = dish_counts.get(name, 0) + 1
            elif t == "eating_out":
                total_out += 1
                if name:
                    out_counts[name] = out_counts.get(name, 0) + 1
            elif t == "order":
                total_order += 1
                if name:
                    order_counts[name] = order_counts.get(name, 0) + 1
            elif t == "nothing":
                total_nothing += 1

        def top10(c: dict) -> list:
            return [{"name": n, "count": v} for n, v in sorted(c.items(), key=lambda x: -x[1])[:10]]

        return self.json({
            "top_dishes": top10(dish_counts),
            "top_eating_out": top10(out_counts),
            "top_order": top10(order_counts),
            "total_days": total_days,
            "total_cooked": total_cooked,
            "total_eating_out": total_out,
            "total_order": total_order,
            "total_nothing": total_nothing,
        })


class MealPlannerHolidaysView(MealPlannerBaseView):
    """GET /api/meal_planner/holidays?from=YYYY-MM-DD&to=YYYY-MM-DD

    Returns {"YYYY-MM-DD": "Holiday Name", ...} for the configured country/state.
    Returns {} when no country is configured or the holidays library is unavailable.
    """

    url = "/api/meal_planner/holidays"
    name = "api:meal_planner:holidays"

    async def get(self, request: web.Request) -> web.Response:
        entry: ConfigEntry | None = self.hass.data.get(DOMAIN, {}).get("entry")
        if entry is None:
            return self.json({})

        country = (entry.options.get("holiday_country") or "").strip()
        state = (entry.options.get("holiday_state") or "").strip()
        if not country:
            return self.json({})

        from_param = request.query.get("from")
        to_param = request.query.get("to")
        try:
            from_date = date.fromisoformat(from_param) if from_param else date.today()
            to_date = date.fromisoformat(to_param) if to_param else from_date + timedelta(days=21)
        except (TypeError, ValueError):
            return self.json({})

        if to_date < from_date or (to_date - from_date).days > 366:
            return self.json({})

        # Compute holidays in executor — the holidays library does some I/O on first import
        result = await self.hass.async_add_executor_job(
            _compute_holidays, country, state, from_date, to_date,
        )
        return self.json(result)


def _compute_holidays(country: str, state: str, from_date: date, to_date: date) -> dict[str, str]:
    """Build a {iso_date: name} mapping for the given range. Safe to call in executor."""
    try:
        import holidays as _holidays_lib
    except ImportError:
        _LOGGER.warning("python-holidays library not available")
        return {}

    years = list(range(from_date.year, to_date.year + 1))
    try:
        kwargs = {"years": years}
        # State only applies for Germany in our supported set
        if country == "DE" and state:
            kwargs["subdiv"] = state
        cal = _holidays_lib.country_holidays(country, **kwargs)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Failed to load holidays for %s/%s: %s", country, state, err)
        return {}

    result: dict[str, str] = {}
    d = from_date
    while d <= to_date:
        name = cal.get(d)
        if name:
            result[d.isoformat()] = name
        d += timedelta(days=1)
    return result
