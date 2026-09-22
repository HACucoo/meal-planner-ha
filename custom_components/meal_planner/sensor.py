"""Sensor platform for Meal Planner – today's and tomorrow's meal."""
from __future__ import annotations

from datetime import date, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MealPlannerConfigEntry
from .const import DOMAIN, PANEL_TITLE

# State texts are *data*, so they follow the integration's language option.
# Entity names are translated by Home Assistant itself (strings.json).
_STATE_I18N: dict[str, dict[str, str]] = {
    "de": {
        "type_eating_out": "Auswärts",
        "type_order": "Bestellen",
        "type_nothing": "Kein Kochen",
        "not_planned": "Nicht geplant",
        "summary": "Heute gibt es {today}. Morgen gibt's {tomorrow}.",
    },
    "en": {
        "type_eating_out": "Eating out",
        "type_order": "Ordering",
        "type_nothing": "No cooking",
        "not_planned": "Not planned",
        "summary": "Today we're having {today}. Tomorrow it's {tomorrow}.",
    },
}


def _strings(entry: MealPlannerConfigEntry) -> dict[str, str]:
    """Return the state-text table for the configured language."""
    return _STATE_I18N.get(entry.options.get("lang", "de"), _STATE_I18N["de"])


def _meal_label(entry: MealPlannerConfigEntry, offset: int) -> str:
    """Return the meal label for today+offset."""
    strings = _strings(entry)
    target = (date.today() + timedelta(days=offset)).isoformat()
    plan_entry = entry.runtime_data.data.get("meal_plan", {}).get(target)
    if not plan_entry:
        return strings["not_planned"]
    if dish_name := plan_entry.get("dish_name", ""):
        return dish_name
    return strings.get(f"type_{plan_entry.get('type', '')}", strings["not_planned"])


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MealPlannerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Meal Planner sensors."""
    entities: list[SensorEntity] = [
        MealSensor(entry, "today", 0),
        MealSensor(entry, "tomorrow", 1),
        MealSummarySensor(entry),
    ]
    entry.runtime_data.sensors = entities
    async_add_entities(entities)


class MealPlannerSensorBase(SensorEntity):
    """Common wiring: entity naming, device grouping, push updates."""

    _attr_has_entity_name = True
    _attr_should_poll = False  # pushed via async_write_ha_state()

    def __init__(self, entry: MealPlannerConfigEntry) -> None:
        """Link the entity to the Meal Planner service device."""
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=PANEL_TITLE,
            manufacturer="HACucoo",
            entry_type=DeviceEntryType.SERVICE,
        )


class MealSensor(MealPlannerSensorBase):
    """Text sensor showing today's or tomorrow's planned meal."""

    def __init__(
        self, entry: MealPlannerConfigEntry, sensor_id: str, day_offset: int
    ) -> None:
        """Initialise one day sensor."""
        super().__init__(entry)
        # unique_id is unchanged on purpose: existing entity_ids survive the upgrade
        self._attr_unique_id = f"{DOMAIN}_{sensor_id}"
        self._attr_translation_key = sensor_id
        self._day_offset = day_offset

    @property
    def native_value(self) -> str:
        """Return the meal planned for this sensor's day."""
        return _meal_label(self._entry, self._day_offset)


class MealSummarySensor(MealPlannerSensorBase):
    """Single sensor with a full spoken summary."""

    _attr_translation_key = "summary"

    def __init__(self, entry: MealPlannerConfigEntry) -> None:
        """Initialise the summary sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{DOMAIN}_summary"

    @property
    def native_value(self) -> str:
        """Return a spoken-style summary of today and tomorrow."""
        return _strings(self._entry)["summary"].format(
            today=_meal_label(self._entry, 0),
            tomorrow=_meal_label(self._entry, 1),
        )
