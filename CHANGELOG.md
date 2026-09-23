# Changelog

All notable changes to this project are documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/).

## [1.8.0] - 2026-09-23

### Added
- **Upcoming meals card** (`custom:meal-planner-upcoming-card`): the next
  meals as slim rows, each filled with the photo of its dish or place, with
  weekday and date, the name, a badge for eating out / order, and Today /
  Tomorrow / in N days on the right.
  - Tapping it opens the Meal Planner panel (`navigate: false` turns that off).
  - Visual editor: heading, number of days (1–21), which day badges to show
    (`relative: all | near | none`), whether to list empty days.
  - Shipped in the existing `meal-planner-card.js`, so no additional resource
    is loaded on every dashboard, and kept free of CSS that old wall-tablet
    browsers lack.
- **Photos for eating out and ordering.** The picture belongs to the name of
  the day ("Pizzeria Luigi") and shows on every day with that name. Each type
  also has a default photo for unnamed days or names without their own.
  Set from the planned day, or from the new "Eating out & orders" tab in the
  dish manager.
- The planned-day dialog has a photo button, for dishes as well.
- **Crop dialog for photos**, like Home Assistant's own user-picture upload:
  drag, zoom, rotate, square or free crop. Falls back to a direct upload if the
  cropper cannot be loaded.
- Accepting a Surprise me / Chefkoch recipe takes its picture along. A photo
  you set yourself is never replaced.

### Changed
- **Today stands out**: accent border, halo, a slight lift, a "Today" badge
  in place of the weekday, and its photo is shown undimmed. Upcoming days are dimmed less than past ones.
- **Day cards are square.** From 1024 px up the grid is only as wide as
  three rows of squares can be tall, so it still never forces a scrollbar.
  Narrower tablets show four columns instead of seven, where square cards
  would have been too small for the text.
- **Weekends get a thicker border** in the card's usual colour. A holiday on
  a weekend adds its amber ring on top.
- **Statistics show everything**: all dishes, restaurants and delivery
  services instead of a top 10, each with how often and when last, sortable
  by clicking a column header. The `/api/meal_planner/stats` response now has
  `dishes`, `eating_out` and `order` lists (with `last_used`) in place of the
  `top_*` keys, and names that differ only in upper/lower case count together.

### Fixed
- The panel loaded all data twice on every open (Alpine called `init()` on
  its own and once more through `x-init`).
- Hovering a holiday card no longer hides its ring.
- After copying new files without restarting Home Assistant, saving a photo
  for eating out / order failed with a bare 404. The panel now hides that
  button while the old backend still runs and says a restart is needed.

## [1.7.0] - 2026-09-22

### Added
- **Dish photos.** A dish can carry a picture, set and replaced from the dish
  list. The photo appears behind that day's card, dimmed, with the weekday and
  the meal name on translucent bubbles so they stay readable on bright images.
  The day dialog shows it as a banner. Photos are entirely optional: a
  text-only dish list keeps working unchanged.
  - Pictures are downscaled in the browser (longest edge 1000 px, JPEG) before
    upload, so no image library is needed on the Home Assistant side.
  - Stored in `config/meal_planner_images/`, so they are part of HA backups.
  - Deleting a dish, or replacing its photo, removes the old file.

### Changed
- **The week overview uses the available screen.** The layout was capped at
  about 900 px wide regardless of the display; it now grows to 1500 px.
- **Cards are much larger** and their height follows the viewport, so the three
  rows fill a wall tablet without ever forcing a scrollbar.
- Larger day numbers and meal names, and up to three lines per meal, so dish
  names are far less likely to be cut off.

## [1.6.0] - 2026-09-22

Alignment with the Home Assistant integration standards (Quality Scale).
Existing entity IDs are unchanged, so dashboards and automations keep working.

### Added
- The three sensors are now grouped under a **Meal Planner** service device
  instead of floating around without one.
- Entity names and icons are provided through Home Assistant's own translation
  and icon files, so they follow the HA interface language.

### Changed
- Runtime state moved to `ConfigEntry.runtime_data`; the integration no longer
  writes to the shared `hass.data` dictionary.
- `strings.json` is now the English source file, as Home Assistant expects.
  German text lives in `translations/de.json` only.
- Options flow and sensor entities updated to current Home Assistant patterns
  (no manually stored config entry, no manual `hass` assignment).

### Fixed
- The API answers **503** while the integration is unloaded or being reloaded.
  Previously those requests hit a missing data structure and failed with an
  internal error, which could happen during an options change.
- A state update can no longer be pushed to a sensor that has not finished
  being added.

## [1.5.0] - 2026-06-10

### Changed
- Dish usage (`use_count` / `last_used`) is now derived from the meal plan
  itself after every change. Editing, moving, swapping or deleting days
  corrects the counters immediately — including moves across the today
  boundary — and historical drift is healed automatically on startup.
- Option changes (language, holiday country/state) apply immediately; the
  integration reloads itself instead of requiring an HA restart.
- A dish blocked for 2 weeks is suggested again for days *after* the block
  expires (the block is checked against the day being planned, not today).
- Internal: all API views share a common base class; duplicated set-up code
  removed.

### Fixed
- Lovelace list card: the refresh timer now survives the card being detached
  and re-attached (e.g. when switching dashboard tabs).
- Malformed JSON bodies and oversized date ranges return proper 400 errors
  instead of crashing with a 500.
- CSV export guards against spreadsheet formula injection (leading `=`, `+`,
  `-`, `@` in dish names).
- Removed the invalid `platforms` key from the manifest.
- README no longer mentions the removed in-header language toggle.

### Added
- Escape closes the topmost modal (move picker → day dialog → dish manager /
  statistics).

## [1.4.1] - 2026-06-05

### Fixed
- `last_used` no longer regresses when (re)planning a dish for an older date,
  so the "least recently cooked" suggestion order stays correct.
- Cooking statistics now count only past/today (actually cooked) days instead
  of treating future-planned days as already cooked.

### Changed
- Code-review cleanups: removed dead imports, used the `TYPE_*` constants in the
  day endpoint, dropped stale comments and simplified a redundant `except`.
- The options dialog only shows the federal-state field when the country is Germany.
- The Lovelace list card re-renders when a meal-planner sensor changes, not only
  every 5 minutes.

## [1.4.0] - 2026-06-05

### Added
- **Move / swap a planned day** — the detail view of any planned day now has a
  *"Move / swap"* link. It opens a picker showing the selected date ±7 days with
  each day's current meal. Choosing an **empty** day moves the entry there and
  clears the original day; choosing an **occupied** day **swaps** the two entries.
- Backend endpoint `POST /api/meal_planner/plan/{day}/move` that relocates or
  swaps plan entries atomically, without touching cooking statistics
  (`use_count` / `last_used`) — so re-organising the plan never double-counts.
  The visible cooking statistics are computed live from the plan and therefore
  always reflect moved/swapped meals.

### Changed
- **Reordered the day planning dialog** for a faster everyday flow: the
  custom-entry field (with the A–Z dish dropdown, *"add to list"* and *Save*) is
  now at the top, followed by quick-select, then the suggestions list, with the
  two *"Surprise me"* buttons at the bottom.

## [1.3.0] - 2026-05-19

### Added
- Public-holiday markers in the day overview (configurable country / region).

## [1.2.0] - 2026-04-23

### Added
- Optional free-text label for *"Eating out"* and *"Order"* entries.

### Changed
- Light-mode design optimisation and statistics refinements.

## [1.1.0] - 2026-04-12

### Added
- Statistics page with a top-10 bar chart.
- Language option (DE / EN) in the integration settings.
- Home Assistant theme integration — colours follow the active HA theme.

### Fixed
- Sensors now refresh at midnight; plus mobile-layout, auth and `last_used` fixes.

## [1.0.0] - 2026-03-28

### Added
- Initial release: rolling 21-day planner, smart suggestions, dish manager
  (incl. bulk edit), quick-select, *"Surprise me"* (TheMealDB) and Chefkoch
  random recipes, summary sensors, Lovelace list card, CSV history export and
  DE / EN localisation.

[1.7.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.7.0
[1.6.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.6.0
[1.5.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.5.0
[1.4.1]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.4.1
[1.4.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.4.0
[1.3.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.3.0
[1.2.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.2.0
[1.1.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.1.0
[1.0.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.0.0
