/**
 * Meal Planner Lovelace cards. Both live in this one module on purpose:
 * Lovelace loads every registered resource on every dashboard, so a second
 * file would cost every wall tablet in the house.
 *
 * Installation:
 *   1. Add the resource in your dashboard:
 *      URL:  /meal_planner_frontend/meal-planner-card.js
 *      Type: JavaScript module
 *   2. Add a card:
 *
 * custom:meal-planner-list-card — compact 7-day list (yesterday → +5 days)
 *   title: "Diese Woche"   <- card heading (omit to hide)
 *   lang: "de"             <- "de" or "en" (default: browser language)
 *
 * custom:meal-planner-upcoming-card — the next meals as slim rows, each
 * filled with the photo of its dish or place
 *   title: "Nächste Gerichte"  <- card heading (omit to hide)
 *   days: 7                    <- how many days ahead, today included
 *   show_empty: false          <- also list unplanned and "no cooking" days
 *   navigate: true             <- tapping the card opens the Meal Planner panel
 *   lang: "de"
 * All options except lang can also be set in the visual card editor.
 */

const API = '/api/meal_planner';
const IMAGE_BASE = '/meal_planner_images';
const REFRESH_MS = 5 * 60 * 1000;
const PANEL_PATH = '/meal-planner';  // PANEL_URL in const.py

const STRINGS = {
  de: {
    weekdays: ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'],
    notPlanned: 'Nicht geplant',
    eatingOut: 'Auswärts',
    order: 'Bestellen',
    nothing: 'Kein Kochen',
    today: 'Heute',
    tomorrow: 'Morgen',
    inDays: n => `in ${n} Tagen`,
    nothingUpcoming: 'Noch nichts geplant',
  },
  en: {
    weekdays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    notPlanned: 'Not planned',
    eatingOut: 'Eating out',
    order: 'Order',
    nothing: 'No cooking',
    today: 'Today',
    tomorrow: 'Tomorrow',
    inDays: n => `in ${n} days`,
    nothingUpcoming: 'Nothing planned yet',
  },
};

function toISO(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function esc(str) {
  const el = document.createElement('span');
  el.textContent = str;
  return el.innerHTML;
}

function addDays(date, n) {
  const d = new Date(date);
  d.setDate(date.getDate() + n);
  return d;
}

async function getJSON(url, fallback) {
  try {
    const resp = await fetch(url);
    return resp.ok ? await resp.json() : fallback;
  } catch (e) {
    console.error('[meal-planner-card] fetch failed', url, e);
    return fallback;
  }
}

/**
 * Shared plumbing: re-render when a meal-planner sensor changes, and every
 * five minutes so the cards roll over at midnight.
 */
class MealPlannerBaseCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._refreshTimer = null;
  }

  setConfig(config) {
    this._config = config || {};
    if (this._initialized) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._stateSig = this._mealSensorSignature(hass);
      this._render();
      this._refreshTimer = setInterval(() => this._render(), REFRESH_MS);
      return;
    }
    // Re-render promptly when a meal-planner sensor changes (e.g. today/tomorrow edited)
    const sig = this._mealSensorSignature(hass);
    if (sig !== this._stateSig) {
      this._stateSig = sig;
      this._render();
    }
  }

  _mealSensorSignature(hass) {
    if (!hass || !hass.states) return '';
    return Object.keys(hass.states)
      .filter(id => id.startsWith('sensor.meal_planner_'))
      .sort()
      .map(id => `${id}=${hass.states[id].state}`)
      .join('|');
  }

  connectedCallback() {
    // Restore the refresh timer after the card is re-attached (e.g. tab switch)
    if (this._initialized && !this._refreshTimer) {
      this._render();
      this._refreshTimer = setInterval(() => this._render(), REFRESH_MS);
    }
  }

  disconnectedCallback() {
    if (this._refreshTimer) {
      clearInterval(this._refreshTimer);
      this._refreshTimer = null;
    }
  }

  _strings() {
    const lang = this._config.lang
      || ((navigator.language || 'de').startsWith('de') ? 'de' : 'en');
    return STRINGS[lang] || STRINGS.de;
  }

  _titleHTML() {
    return this._config.title
      ? `<div class="title">${esc(this._config.title)}</div>`
      : '';
  }
}

// ── Compact list ──────────────────────────────────────────────────────────

class MealPlannerListCard extends MealPlannerBaseCard {
  async _render() {
    const S = this._strings();
    const today = new Date();
    const todayISO = toISO(today);

    const plan = await getJSON(
      `${API}/plan?from=${toISO(addDays(today, -1))}&to=${toISO(addDays(today, 5))}`, {}
    );

    const days = [];
    for (let i = -1; i <= 5; i++) {
      const d = addDays(today, i);
      const iso = toISO(d);
      const wi  = (d.getDay() + 6) % 7; // 0=Mon … 6=Sun
      const entry = plan[iso];
      let text = S.notPlanned;
      if (entry) {
        const typeLabel = { eating_out: S.eatingOut, order: S.order, nothing: S.nothing };
        text = entry.dish_name || typeLabel[entry.type] || S.notPlanned;
      }
      days.push({ iso, weekday: S.weekdays[wi], text, isToday: iso === todayISO });
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 16px 16px 8px; }
        .title {
          font-size: 0.95rem;
          font-weight: 600;
          color: var(--primary-text-color);
          margin-bottom: 10px;
          padding-bottom: 8px;
          border-bottom: 1px solid var(--divider-color);
        }
        .row {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 7px 0;
          border-bottom: 1px solid var(--divider-color);
        }
        .row:last-child { border-bottom: none; }
        .wd {
          font-size: 0.72rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          color: var(--secondary-text-color);
          width: 26px;
          flex-shrink: 0;
        }
        .meal {
          font-size: 0.875rem;
          color: var(--primary-text-color);
        }
        .today .wd  { color: var(--primary-color); }
        .today .meal { color: var(--primary-color); font-weight: 600; }
        .empty { color: var(--disabled-text-color); }
      </style>
      <ha-card>
        ${this._titleHTML()}
        ${days.map(d => `
          <div class="row${d.isToday ? ' today' : ''}">
            <span class="wd">${esc(d.weekday)}</span>
            <span class="meal${d.text === S.notPlanned ? ' empty' : ''}">${esc(d.text)}</span>
          </div>
        `).join('')}
      </ha-card>
    `;
  }

  getCardSize() { return 5; }
}

// ── Upcoming meals with photos ────────────────────────────────────────────

const TYPE_STYLE = {
  dish:       { icon: '🍽️', cls: 'dish' },
  custom:     { icon: '🍽️', cls: 'dish' },
  eating_out: { icon: '🍴', cls: 'out' },
  order:      { icon: '📦', cls: 'order' },
  nothing:    { icon: '🚫', cls: 'none' },
};

class MealPlannerUpcomingCard extends MealPlannerBaseCard {
  constructor() {
    super();
    // One listener on the host survives every re-render of the shadow DOM
    this.addEventListener('click', () => this._openPanel());
    this.addEventListener('keydown', ev => {
      if (ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault();
        this._openPanel();
      }
    });
  }

  static getStubConfig() {
    return { days: 7 };
  }

  static getConfigElement() {
    return document.createElement('meal-planner-upcoming-card-editor');
  }

  _navigates() {
    // Not while the dashboard is being edited or the card is a preview in the editor
    return this._config.navigate !== false && !this.editMode && !this.preview;
  }

  _openPanel() {
    if (!this._navigates()) return;
    // How Home Assistant's own navigate action switches pages without a reload
    history.pushState(null, '', PANEL_PATH);
    window.dispatchEvent(new CustomEvent('location-changed', { detail: { replace: false } }));
  }

  _imageResolver(dishes, places) {
    // Same lookup as the panel: dish by id or name; a place by its own
    // photo, else the default photo of its type
    const dishById = {}, dishByName = {}, placeByKey = {};
    for (const d of dishes) {
      dishById[d.id] = d;
      dishByName[d.name.trim().toLowerCase()] = d;
    }
    for (const p of places) {
      if (p.image) placeByKey[`${p.type}:${p.name.trim().toLowerCase()}`] = p;
    }
    const url = rec => (rec && rec.image ? `${IMAGE_BASE}/${encodeURIComponent(rec.image)}` : '');
    return entry => {
      const name = (entry.dish_name || '').trim().toLowerCase();
      if (entry.type === 'dish' || entry.type === 'custom') {
        return url(dishById[entry.dish_id] || dishByName[name]);
      }
      if (entry.type === 'eating_out' || entry.type === 'order') {
        return url(placeByKey[`${entry.type}:${name}`] || placeByKey[`${entry.type}:`]);
      }
      return '';
    };
  }

  async _render() {
    const S = this._strings();
    const lang = this._config.lang
      || ((navigator.language || 'de').startsWith('de') ? 'de' : 'en');
    const days = Math.max(1, Math.min(21, Number(this._config.days) || 7));
    const showEmpty = !!this._config.show_empty;
    const today = new Date();

    const [plan, dishes, places] = await Promise.all([
      getJSON(`${API}/plan?from=${toISO(today)}&to=${toISO(addDays(today, days - 1))}`, {}),
      getJSON(`${API}/dishes`, []),
      getJSON(`${API}/places`, []),  // older backends: no place photos, rows still render
    ]);
    const imageFor = this._imageResolver(dishes, places);
    const dateFmt = new Intl.DateTimeFormat(lang, { day: '2-digit', month: '2-digit' });

    const rows = [];
    for (let i = 0; i < days; i++) {
      const d = addDays(today, i);
      const entry = plan[toISO(d)];
      const planned = entry && entry.type !== 'nothing';
      if (!planned && !showEmpty) continue;

      const type = entry ? entry.type : null;
      const style = TYPE_STYLE[type] || { icon: '·', cls: 'empty' };
      const typeLabel = { eating_out: S.eatingOut, order: S.order, nothing: S.nothing }[type];
      rows.push({
        offset: i,
        date: `${S.weekdays[(d.getDay() + 6) % 7]} · ${dateFmt.format(d)}`,
        name: entry ? (entry.dish_name || typeLabel || '') : S.notPlanned,
        // Unnamed eating-out / order days already show the type as their name
        badge: entry && entry.dish_name ? (typeLabel || '') : '',
        image: entry ? imageFor(entry) : '',
        style,
      });
    }

    const rel = n => (n === 0 ? S.today : n === 1 ? S.tomorrow : S.inDays(n));

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 12px; }
        ha-card.clickable { cursor: pointer; }
        ha-card.clickable:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
        .title {
          font-size: 0.95rem;
          font-weight: 600;
          color: var(--primary-text-color);
          margin: 2px 2px 10px;
        }
        .list { display: flex; flex-direction: column; gap: 6px; }

        .row {
          position: relative;
          overflow: hidden;
          display: flex;
          align-items: center;
          gap: 10px;
          min-height: 48px;
          padding: 6px 10px 6px 6px;
          border-radius: 10px;
          border: 1px solid var(--divider-color);
          background: var(--secondary-background-color, rgba(127,127,127,0.12));
          color: var(--primary-text-color);
        }
        /* The photo fills the row; a gradient keeps the text side readable.
           No blur or backdrop-filter: cheap enough for an old wall tablet. */
        .bg {
          position: absolute; inset: 0;
          background-size: cover;
          background-position: center;
        }
        .row.has-photo::after {
          content: "";
          position: absolute; inset: 0;
          background: linear-gradient(90deg, rgba(0,0,0,0.86) 0%, rgba(0,0,0,0.62) 55%, rgba(0,0,0,0.30) 100%);
        }
        .row.has-photo { color: #fff; border-color: rgba(255,255,255,0.10); }
        .row > :not(.bg) { position: relative; z-index: 1; }

        /* Rows without a photo get a faint tint of their type. A tint layered
           over the base colour instead of color-mix(), which old tablets lack. */
        .row.t-dish:not(.has-photo)  { background: linear-gradient(rgba(34,197,94,0.14), rgba(34,197,94,0.14)), var(--secondary-background-color, transparent); }
        .row.t-out:not(.has-photo)   { background: linear-gradient(rgba(245,158,11,0.16), rgba(245,158,11,0.16)), var(--secondary-background-color, transparent); }
        .row.t-order:not(.has-photo) { background: linear-gradient(rgba(59,130,246,0.16), rgba(59,130,246,0.16)), var(--secondary-background-color, transparent); }
        .row.t-none, .row.t-empty    { opacity: 0.6; }

        .row.today { border: 2px solid var(--primary-color); padding: 5px 9px 5px 5px; }

        .thumb {
          width: 36px; height: 36px;
          flex-shrink: 0;
          border-radius: 7px;
          background-size: cover;
          background-position: center;
          background-color: rgba(127,127,127,0.25);
          display: flex; align-items: center; justify-content: center;
          font-size: 1.05rem;
          box-shadow: 0 1px 3px rgba(0,0,0,0.4);
        }
        .text { flex: 1; min-width: 0; }
        .meta {
          display: flex; align-items: center; gap: 6px;
          font-size: 0.72rem;
          line-height: 1.2;
          opacity: 0.8;
        }
        .row.has-photo .meta { opacity: 0.9; }
        .name {
          font-size: 0.95rem;
          font-weight: 700;
          line-height: 1.25;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .row.has-photo .name { text-shadow: 0 1px 2px rgba(0,0,0,0.6); }

        .badge {
          font-size: 0.62rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          padding: 1px 6px;
          border-radius: 5px;
          white-space: nowrap;
        }
        /* Solid badges read the same on a photo and on either theme */
        .badge.out   { background: #b45309; color: #fff; }
        .badge.order { background: #1d4ed8; color: #fff; }
        .badge.none  { background: rgba(127,127,127,0.45); color: #fff; }

        .rel {
          flex-shrink: 0;
          font-size: 0.62rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          padding: 2px 7px;
          border-radius: 5px;
          background: rgba(127,127,127,0.28);
          white-space: nowrap;
        }
        .row.has-photo .rel { background: rgba(0,0,0,0.45); }
        .row.today .rel { background: var(--primary-color); color: var(--text-primary-color, #fff); }

        .empty-note {
          color: var(--secondary-text-color);
          font-style: italic;
          font-size: 0.875rem;
          padding: 8px 4px;
        }
      </style>
      <ha-card${this._navigates() ? ' class="clickable" role="button" tabindex="0"' : ''}>
        ${this._titleHTML()}
        <div class="list">
          ${rows.length === 0 ? `<div class="empty-note">${esc(S.nothingUpcoming)}</div>` : ''}
          ${rows.map(r => `
            <div class="row t-${r.style.cls}${r.image ? ' has-photo' : ''}${r.offset === 0 ? ' today' : ''}">
              ${r.image ? `<div class="bg" style="background-image:url('${r.image}')"></div>` : ''}
              <div class="thumb" style="${r.image ? `background-image:url('${r.image}')` : ''}">${r.image ? '' : r.style.icon}</div>
              <div class="text">
                <div class="meta">
                  <span>${esc(r.date)}</span>
                  ${r.badge ? `<span class="badge ${r.style.cls}">${esc(r.badge)}</span>` : ''}
                </div>
                <div class="name">${esc(r.name)}</div>
              </div>
              <span class="rel">${esc(rel(r.offset))}</span>
            </div>
          `).join('')}
        </div>
      </ha-card>
    `;
    this._rowCount = rows.length;
  }

  getCardSize() {
    const rows = typeof this._rowCount === 'number' ? this._rowCount : 5;
    return 1 + Math.ceil(rows * 0.9);
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: 'auto' };
  }
}

// ── Visual editor for the upcoming card ──────────────────────────────────

const EDITOR_LABELS = {
  de: {
    title: 'Überschrift (leer = keine)',
    days: 'Wie viele Tage (ab heute)',
    show_empty: 'Ungeplante Tage und „Kein Kochen“ zeigen',
    navigate: 'Tippen öffnet den Meal Planner',
  },
  en: {
    title: 'Heading (empty = none)',
    days: 'How many days (from today)',
    show_empty: 'Show unplanned and "no cooking" days',
    navigate: 'Tapping opens the Meal Planner',
  },
};

const EDITOR_SCHEMA = [
  { name: 'title', selector: { text: {} } },
  { name: 'days', selector: { number: { min: 1, max: 21, step: 1, mode: 'slider' } } },
  { name: 'show_empty', selector: { boolean: {} } },
  { name: 'navigate', selector: { boolean: {} } },
];

class MealPlannerUpcomingCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  async _ensureHaForm() {
    if (customElements.get('ha-form')) return;
    // ha-form is lazy-loaded; building a built-in card editor pulls it in
    try {
      const helpers = await window.loadCardHelpers();
      const card = await helpers.createCardElement({ type: 'entities', entities: [] });
      await card.constructor.getConfigElement();
    } catch (e) {
      console.warn('[meal-planner-card] could not load ha-form', e);
    }
  }

  async _render() {
    if (!this._config || !this._hass) return;
    if (!this._form) {
      await this._ensureHaForm();
      if (this._form) return;  // another call finished first
      this._form = document.createElement('ha-form');
      this._form.addEventListener('value-changed', ev => {
        const config = { ...this._config, ...ev.detail.value };
        // Keep the YAML tidy: drop what is empty or at its default
        if (!config.title) delete config.title;
        if (!config.show_empty) delete config.show_empty;
        if (config.navigate !== false) delete config.navigate;
        this._config = config;
        this.dispatchEvent(new CustomEvent('config-changed', {
          detail: { config }, bubbles: true, composed: true,
        }));
      });
      this.appendChild(this._form);
    }
    const lang = (this._hass.language || navigator.language || 'de').startsWith('de') ? 'de' : 'en';
    this._form.computeLabel = schema => EDITOR_LABELS[lang][schema.name] || schema.name;
    this._form.hass = this._hass;
    this._form.schema = EDITOR_SCHEMA;
    // Show defaults explicitly, so the slider and toggles start where the card does
    this._form.data = {
      days: 7,
      show_empty: false,
      navigate: true,
      ...this._config,
    };
  }
}

customElements.define('meal-planner-list-card', MealPlannerListCard);
customElements.define('meal-planner-upcoming-card', MealPlannerUpcomingCard);
customElements.define('meal-planner-upcoming-card-editor', MealPlannerUpcomingCardEditor);

window.customCards = window.customCards || [];
window.customCards.push(
  {
    type: 'meal-planner-list-card',
    name: 'Meal Planner Liste',
    description: '7-Tage Listenübersicht (gestern + 5 Tage)',
    preview: false,
  },
  {
    type: 'meal-planner-upcoming-card',
    name: 'Meal Planner – Nächste Gerichte',
    description: 'Die nächsten Gerichte als schmale Zeilen mit Foto',
    preview: false,
  },
);
