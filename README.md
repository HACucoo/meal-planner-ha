# 🍽️ Meal Planner for Home Assistant

A HACS integration that adds a touch-friendly dinner planner to your Home Assistant sidebar — perfect for a family dashboard on a tablet or wall display.

![Meal Planner Screenshot](https://raw.githubusercontent.com/HACucoo/meal-planner-ha/main/screenshot.png)

## Features

- **Rolling 21-day view** — always shows yesterday−2 through today+18, no manual week navigation needed
- **Responsive grid** — 3 × 7 layout on tablet/desktop, 2-column on mobile
- **Smart suggestions** — randomly picked from the 10 dishes cooked longest ago, so you always get variety
- **Accept / Skip / Block** — skip a dish just for today (↷), block it for 2 weeks (✕), or accept it (✓); accepted dishes get historized
- **Dish picker dropdown** — A–Z sorted list of all your dishes right in the day modal, alongside the free-text field
- **Quick-select** — one tap for No cooking, Eating out, or Order delivery
- **Surprise me 🎲** — fetches a random recipe from [TheMealDB](https://www.themealdb.com/) (free, no API key needed)
- **Chefkoch 👨‍🍳** — pulls a random German recipe (name + image) from Chefkoch's recipe API
- **Dish manager** — add, remove, or bulk-edit your dish list; blocked dishes can be unblocked early
- **History export** — download your full meal history as CSV
- **DE / EN localisation** — auto-detected from browser language, toggle button in the header
- **Persistent storage** — all data saved in Home Assistant's `.storage/` directory

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
| Plan a day | Tap any day card |
| Accept a suggestion | Tap ✓ next to a dish |
| Skip suggestion (today only) | Tap ↷ — dish stays in pool, not suggested again this session |
| Block suggestion (2 weeks) | Tap ✕ — dish won't appear for 14 days |
| Pick from your list | Use the A–Z dropdown next to the text field |
| Eating out / Delivery / No cooking | Tap the quick-select buttons |
| Own entry | Type in the free-text field, optionally save to list |
| Surprise me | Tap 🎲 for a random TheMealDB recipe, or 👨‍🍳 for a random Chefkoch recipe |
| Edit a planned day | Tap the day card → "Change" |
| Manage dish list | Tap "Manage dish list" at the bottom |
| Switch language | Tap DE / EN button in the header |
| Export history | Tap "History as CSV" at the bottom |

---

## How suggestions work

Every dish stores a `last_used` date. The 10 dishes cooked longest ago (never-cooked ones first) form a candidate pool — 3 are picked randomly from that pool each time the modal opens, so you won't always see the same three suggestions.

- **↷ Not today** — dish is skipped for the current planning session only; no data is changed
- **✕ 2 weeks not** — dish gets a `blocked_until` date (today + 14 days) and won't appear in suggestions until then; can be lifted early in the dish manager

---

## Requirements

- Home Assistant 2023.x or newer
- HACS (for one-click install)
- Internet access on your HA instance (needed for Surprise me / Chefkoch features)

---

## Contributing

PRs welcome! Please open an issue first for larger changes.

## License

MIT
