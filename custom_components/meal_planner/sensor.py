"""Sensor platform for Meal Planner – today's and tomorrow's meal."""
from __future__ import annotations

from datetime import date, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_I18N = {
    "de": {
        "type_eating_out": "Auswärts",
        "type_order": "Bestellen",
        "type_nothing": "Kein Kochen",
        "not_planned": "Nicht geplant",
        "name_today": "Meal Planner Heute",
        "name_tomorrow": "Meal Planner Morgen",
        "name_summary": "Meal Planner Zusammenfassung",
        "summary": "Heute gibt es {today}. Morgen gibt's {tomorrow}.",
    },
    "en": {
        "type_eating_out": "Eating out",
        "type_order": "Ordering",
        "type_nothing": "No cooking",
        "not_planned": "Not planned",
        "name_today": "Meal Planner Today",
        "name_tomorrow": "Meal Planner Tomorrow",
        "name_summary": "Meal Planner Summary",
        "summary": "Today we're having {today}. Tomorrow it's {tomorrow}.",
    },
}


def _get_lang(hass: HomeAssistant) -> str:
    entry = hass.data.get(DOMAIN, {}).get("entry")
    return entry.options.get("lang", "de") if entry else "de"


def _strings(hass: HomeAssistant) -> dict:
    return _I18N.get(_get_lang(hass), _I18N["de"])


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Meal Planner sensors."""
    entities: list[SensorEntity] = [
        MealSensor(hass, "today",    0),
        MealSensor(hass, "tomorrow", 1),
        MealSummarySensor(hass),
    ]
    hass.data[DOMAIN]["sensors"] = entities
    async_add_entities(entities)


def _meal_label(hass: HomeAssistant, data: dict, offset: int) -> str:
    """Return the meal label for today+offset."""
    S = _strings(hass)
    target = (date.today() + timedelta(days=offset)).isoformat()
    entry = data.get("meal_plan", {}).get(target)
    if not entry:
        return S["not_planned"]
    dish_name = entry.get("dish_name", "")
    if dish_name:
        return dish_name
    type_key = f"type_{entry.get('type', '')}"
    return S.get(type_key, S["not_planned"])


class MealSensor(SensorEntity):
    """Text sensor showing today's or tomorrow's planned meal."""

    _attr_icon = "mdi:food"
    _attr_should_poll = False  # pushed via async_write_ha_state()

    def __init__(
        self,
        hass: HomeAssistant,
        sensor_id: str,
        day_offset: int,
    ) -> None:
        self.hass = hass
        self._attr_unique_id = f"{DOMAIN}_{sensor_id}"
        self._sensor_id = sensor_id
        self._day_offset = day_offset

    @property
    def name(self) -> str:
        S = _strings(self.hass)
        key = "name_today" if self._sensor_id == "today" else "name_tomorrow"
        return S[key]

    @property
    def native_value(self) -> str:
        """Return the meal name for the target day."""
        data = self.hass.data.get(DOMAIN, {}).get("data", {})
        return _meal_label(self.hass, data, self._day_offset)


class MealSummarySensor(SensorEntity):
    """Single sensor with a full spoken summary."""

    _attr_icon = "mdi:silverware-fork-knife"
    _attr_should_poll = False
    _attr_unique_id = f"{DOMAIN}_summary"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    @property
    def name(self) -> str:
        return _strings(self.hass)["name_summary"]

    @property
    def native_value(self) -> str:
        S = _strings(self.hass)
        data = self.hass.data.get(DOMAIN, {}).get("data", {})
        today = _meal_label(self.hass, data, 0)
        tomorrow = _meal_label(self.hass, data, 1)
        return S["summary"].format(today=today, tomorrow=tomorrow)
