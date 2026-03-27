# 🍽️ Meal Planner for Home Assistant

A HACS integration that adds a touch-friendly weekly dinner planner to your Home Assistant sidebar — perfect for a family dashboard.

![Meal Planner Screenshot](https://raw.githubusercontent.com/HACucoo/meal-planner-ha/main/screenshot.png)

## Features

- **Weekly overview** — see all 7 days at a glance, navigate between weeks
- **Smart suggestions** — 3 dishes per day, always pulled from the ones cooked longest ago
- **Accept / Skip / Block** — skip a dish just for today (↷), block it for 2 weeks (✕), or accept it (✓); accepted dishes get historized
- **Quick-select** — one tap for "Kein Kochen", "Auswärts" (eating out), or "Bestellen" (delivery)
- **Free text** — type any dish name; optionally add it permanently to the list
- **Surprise me 🎲** — fetches a random recipe from [TheMealDB](https://www.themealdb.com/) (free, no API key needed)
- **Dish manager** — add or remove dishes from the list at any time
- **Persistent storage** — all data is saved in Home Assistant's `.storage/` directory

---

## Installation via HACS

1. Open HACS → **Integrations** → three-dot menu → **Custom repositories**
2. Add `https://github.com/HACucoo/meal-planner-ha` with category **Integration**
3. Search for "Meal Planner" and install
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration** → search for **Meal Planner**
6. A new **Meal Planner** entry will appear in the sidebar

---

## Manual Installation

1. Copy the `custom_components/meal_planner` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant
3. Add the integration via **Settings → Devices & Services**

---

## Usage

| Action | How |
|---|---|
| Plan a day | Tap on any day card |
| Accept a suggestion | Tap ✓ next to a dish |
| Skip suggestion (today only) | Tap ↷ — dish stays in pool, not suggested again this session |
| Block suggestion (2 weeks) | Tap ✕ — dish won't appear for 14 days |
| Eating out / Delivery | Tap the quick-select buttons |
| No cooking needed | Tap 🚫 Kein Kochen |
| Own entry | Type in the free-text field, optionally save to list |
| Surprise me | Tap 🎲 — pulls a random recipe from TheMealDB |
| Edit a planned day | Tap the day card, then "Ändern" |
| Manage dish list | Tap "Gerichtliste verwalten" at the bottom |

---

## How suggestions work

Every dish stores a `last_used` date. Suggestions are always sorted by `last_used` ascending — dishes never cooked appear first, then those cooked longest ago.

- **↷ Nicht heute** — dish is skipped for the current planning session only; no data is changed
- **✕ 2 Wochen nicht** — dish gets a `blocked_until` date (today + 14 days) and won't appear in suggestions until then; can be lifted early in the dish manager

---

## Requirements

- Home Assistant 2023.x or newer
- HACS (for one-click install)
- Internet access on your HA instance (only needed for the "Surprise me" feature via TheMealDB)

---

## Contributing

PRs welcome! Please open an issue first for larger changes.

## License

MIT
