# Changelog

All notable changes to this project are documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/).

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

[1.5.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.5.0
[1.4.1]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.4.1
[1.4.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.4.0
[1.3.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.3.0
[1.2.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.2.0
[1.1.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.1.0
[1.0.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.0.0
