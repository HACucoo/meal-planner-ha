# 🍽️ Meal Planner for Home Assistant

A HACS integration that adds a touch-friendly dinner planner to your Home Assistant sidebar — perfect for a family dashboard on a tablet or wall display.

<img width="938" height="1032" alt="image" src="https://github.com/user-attachments/assets/d4b5da35-7e66-4d43-b533-090f1d73ca01" />

## Features

- **Rolling 21-day view** — always shows yesterday−2 through today+18, no manual week navigation needed
- **Responsive grid** — square cards, 3 × 7 on landscape tablets and desktops, 4 columns on portrait tablets, 2 on phones; today is highlighted, weekends get a thicker border and holidays an amber ring
- **Smart suggestions** — randomly picked from the 10 dishes cooked longest ago, so you always get variety
- **Accept / Skip / Block** — skip a dish just for today (↷), block it for 2 weeks (✕), or accept it (✓); accepted dishes get historized
- **Dish picker dropdown** — A–Z sorted list of all your dishes right in the day modal, alongside the free-text field
- **Quick-select** — one tap for No cooking, Eating out, or Order delivery
- **Move / swap days** — on any planned day, move the meal to another date or swap two days within a ±7-day window
- **Surprise me 🎲** — fetches a random recipe from [TheMealDB](https://www.themealdb.com/) (free, no API key needed)
- **Chefkoch 👨‍🍳** — pulls a random German recipe (name + image) from Chefkoch's recipe API
- **Dish manager** — add, remove, or bulk-edit your dish list; blocked dishes can be unblocked early
- **Photos** — give a dish, a restaurant or a delivery service a picture and it appears behind that day's card, with the text on translucent bubbles; entirely optional, a plain text-only list keeps working
- **Statistics** — every dish, restaurant and delivery service ever planned, sortable by name, how often and when last
- **History export** — download your full meal history as CSV
- **DE / EN localisation** — configured in the integration options (browser language as fallback)
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
| Move or swap a planned meal | Tap the day card → "Move / swap", then pick a day (empty = move, occupied = swap) |
| Manage dish list | Tap "Manage dish list" at the bottom |
| Add or change a dish photo | Manage dish list → tap the tile to the left of the dish |
| Remove a dish photo | Manage dish list → tap 🚫 on that row |
| Photo for eating out / order | Tap the planned day → "Add photo", or Manage dish list → "Eating out & orders" |
| Statistics | Tap "Statistics" at the bottom; tap a column header to sort, again to flip the order |
| Switch language | Settings → Devices & Services → Meal Planner → Configure |
| Export history | Tap "History as CSV" at the bottom |

---

## Photos

Photos are optional. A day without one looks exactly as before, so you can keep everything as plain text.

- How strongly a photo is dimmed depends on the day: past days are dimmed the most, upcoming days less, and today shows its photo at full strength.
- Eating out and ordering have no dish, so their photo belongs to the **name** you gave the day ("Pizzeria Luigi", "Sushi Bar") and shows on every day with that name. Each type also has a **default photo** for days without a name, or whose name has no photo of its own. Both can be set from the planned day or from Manage dish list → "Eating out & orders".

- Picking a file opens a **crop dialog**, the same idea as Home Assistant's own user-picture upload: drag the frame, pinch or scroll to zoom, rotate, and switch between a square and a free crop. If the cropper cannot be loaded, the photo is uploaded uncropped instead of blocking you.
- Pictures are scaled down **in the browser** before upload (longest edge 1000 px, JPEG), so a phone photo arrives as a few dozen kilobytes and no image library is needed on the Home Assistant side.
- They are stored in `config/meal_planner_images/` and are therefore included in Home Assistant backups.
- A photo belongs to its dish. Renaming a dish in **bulk edit** counts as deleting one dish and creating another, so the photo is lost. Renaming the dish row itself keeps it.
- Accepting a **Surprise me** or **Chefkoch** recipe takes its picture along automatically. A photo you set yourself is never overwritten by this, and only those two recipe sources may be downloaded from.

---

## How suggestions work

Every dish stores a `last_used` date. The 10 dishes cooked longest ago (never-cooked ones first) form a candidate pool — 3 are picked randomly from that pool each time the modal opens, so you won't always see the same three suggestions.

- **↷ Not today** — dish is skipped for the current planning session only; no data is changed
- **✕ 2 weeks not** — dish gets a `blocked_until` date (today + 14 days) and won't appear in suggestions until then; can be lifted early in the dish manager

---

## Sensors

After setup, three text sensors are available, grouped under a **Meal Planner** device:

| Entity | Value |
|---|---|
| Today | Today's planned meal (dish name, or "Eating out" / "Order" / "No cooking" / "Not planned") |
| Tomorrow | Tomorrow's planned meal (same format) |
| Summary | One spoken-style sentence covering today and tomorrow, handy for TTS |

These update instantly whenever a day is saved, moved, or cleared in the planner. Use them in automations, dashboards, or display cards.

The entity IDs are generated from the Home Assistant interface language when the integration is first set up, so a German instance gets `sensor.meal_planner_heute` and an English one `sensor.meal_planner_today`. Existing IDs never change on update. The sensor **state** text follows the language chosen in the integration options.

---

## Lovelace List Card

A compact 7-day list card is included — ideal for a portrait sidebar or a small dashboard tile.

**1. Register the resource (once per dashboard)**

Go to your dashboard → ⋮ menu → **Edit dashboard** → **Manage resources** → **Add resource**:

| Field | Value |
|---|---|
| URL | `/meal_planner_frontend/meal-planner-card.js` |
| Resource type | JavaScript module |

**2. Add the card**

In the card picker choose **Manual** and paste:

```yaml
type: custom:meal-planner-list-card
title: Diese Woche   # optional heading
lang: de             # optional: "de" or "en" (default: browser language)
```

The card shows **7 days**: yesterday · today (highlighted) · next 5 days, each with a weekday abbreviation and the planned meal. It refreshes automatically every 5 minutes.

---

## Requirements

- Home Assistant 2023.x or newer
- HACS (for one-click install)
- Internet access on your HA instance (needed for Surprise me / Chefkoch features)

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

---

## Contributing

PRs welcome! Please open an issue first for larger changes.

## License

MIT
