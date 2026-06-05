# Changelog

All notable changes to this project are documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/).

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

[1.4.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.4.0
[1.3.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.3.0
[1.2.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.2.0
[1.1.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.1.0
[1.0.0]: https://github.com/HACucoo/meal-planner-ha/releases/tag/v1.0.0
