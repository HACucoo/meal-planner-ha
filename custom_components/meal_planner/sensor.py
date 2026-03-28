"""Sensor platform for Meal Planner – today's and tomorrow's meal."""
from __future__ import annotations

from datetime import date, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_TYPE_LABELS: dict[str, str] = {
    "eating_out": "Auswärts",
    "order": "Bestellen",
    "nothing": "Kein Kochen",
}
_NOT_PLANNED = "Nicht geplant"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Meal Planner sensors."""
    entities: list[SensorEntity] = [
        MealSensor(hass, "today",    "Meal Planner Heute",   0),
        MealSensor(hass, "tomorrow", "Meal Planner Morgen",  1),
        MealSummarysensor(hass),
    ]
    hass.data[DOMAIN]["sensors"] = entities
    async_add_entities(entities)


class MealSensor(SensorEntity):
    """Text sensor showing today's or tomorrow's planned meal."""

    _attr_icon = "mdi:food"
    _attr_should_poll = False  # pushed via async_write_ha_state()

    def __init__(
        self,
        hass: HomeAssistant,
        sensor_id: str,
        name: str,
        day_offset: int,
    ) -> None:
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{sensor_id}"
        self._day_offset = day_offset

    @property
    def native_value(self) -> str:
        """Return the meal name for the target day."""
        target = (date.today() + timedelta(days=self._day_offset)).isoformat()
        data = self.hass.data.get(DOMAIN, {}).get("data", {})
        entry = data.get("meal_plan", {}).get(target)
        if not entry:
            return _NOT_PLANNED
        dish_name = entry.get("dish_name", "")
        if dish_name:
            return dish_name
        return _TYPE_LABELS.get(entry.get("type", ""), _NOT_PLANNED)


def _meal_label(data: dict, offset: int) -> str:
    """Return the meal label for today+offset."""
    target = (date.today() + timedelta(days=offset)).isoformat()
    entry = data.get("meal_plan", {}).get(target)
    if not entry:
        return _NOT_PLANNED
    dish_name = entry.get("dish_name", "")
    if dish_name:
        return dish_name
    return _TYPE_LABELS.get(entry.get("type", ""), _NOT_PLANNED)


class MealSummarysensor(SensorEntity):
    """Single sensor with a full spoken summary: 'Heute gibt es X. Morgen gibt's Y.'"""

    _attr_icon = "mdi:silverware-fork-knife"
    _attr_should_poll = False
    _attr_name = "Meal Planner Zusammenfassung"
    _attr_unique_id = f"{DOMAIN}_summary"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    @property
    def native_value(self) -> str:
        data = self.hass.data.get(DOMAIN, {}).get("data", {})
        today = _meal_label(data, 0)
        tomorrow = _meal_label(data, 1)
        return f"Heute gibt es {today}. Morgen gibt's {tomorrow}."
