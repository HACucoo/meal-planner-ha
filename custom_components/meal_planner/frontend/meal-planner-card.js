/**
 * meal-planner-list-card
 * Lovelace card: compact 7-day list (yesterday → +5 days), today highlighted.
 *
 * Installation:
 *   1. Add the resource in your dashboard:
 *      URL:  /meal_planner_frontend/meal-planner-card.js
 *      Type: JavaScript module
 *   2. Add a card with type: custom:meal-planner-list-card
 *
 * Optional config:
 *   title: "Diese Woche"   <- card heading (omit to hide)
 *   lang: "de"             <- "de" or "en" (default: browser language)
 */

const STRINGS = {
  de: {
    weekdays: ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'],
    notPlanned: 'Nicht geplant',
    eatingOut: 'Auswärts',
    order: 'Bestellen',
    nothing: 'Kein Kochen',
  },
  en: {
    weekdays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    notPlanned: 'Not planned',
    eatingOut: 'Eating out',
    order: 'Order',
    nothing: 'No cooking',
  },
};

function toISO(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

class MealPlannerListCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._refreshTimer = null;
  }

  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._render();
      // Refresh every 5 minutes so the card stays current after midnight
      this._refreshTimer = setInterval(() => this._render(), 5 * 60 * 1000);
    }
  }

  disconnectedCallback() {
    if (this._refreshTimer) clearInterval(this._refreshTimer);
  }

  _strings() {
    const lang = this._config.lang
      || (navigator.language || 'de').startsWith('de') ? 'de' : 'en';
    return STRINGS[lang] || STRINGS.de;
  }

  async _render() {
    const S = this._strings();
    const today = new Date();
    const todayISO = toISO(today);

    const fromDate = new Date(today); fromDate.setDate(today.getDate() - 1);
    const toDate   = new Date(today); toDate.setDate(today.getDate() + 5);
    const fromISO  = toISO(fromDate);
    const toISO_   = toISO(toDate);

    let plan = {};
    try {
      const resp = await fetch(`/api/meal_planner/plan?from=${fromISO}&to=${toISO_}`);
      if (resp.ok) plan = await resp.json();
    } catch (e) {
      console.error('[meal-planner-card] fetch failed', e);
    }

    const days = [];
    for (let i = -1; i <= 5; i++) {
      const d = new Date(today);
      d.setDate(today.getDate() + i);
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

    const title = this._config.title
      ? `<div class="title">${this._config.title}</div>`
      : '';

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
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .today .wd  { color: var(--primary-color); }
        .today .meal { color: var(--primary-color); font-weight: 600; }
        .empty { color: var(--disabled-text-color); }
      </style>
      <ha-card>
        ${title}
        ${days.map(d => `
          <div class="row${d.isToday ? ' today' : ''}">
            <span class="wd">${d.weekday}</span>
            <span class="meal${d.text === S.notPlanned ? ' empty' : ''}">${d.text}</span>
          </div>
        `).join('')}
      </ha-card>
    `;
  }

  getCardSize() { return 5; }
}

customElements.define('meal-planner-list-card', MealPlannerListCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'meal-planner-list-card',
  name: 'Meal Planner Liste',
  description: '7-Tage Listenübersicht (gestern + 5 Tage)',
  preview: false,
});
