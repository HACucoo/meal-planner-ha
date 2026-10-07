"""Development server: the panel and cards against the REAL backend code.

Stubs just enough of aiohttp / homeassistant to import the integration, seeds
demo data (dishes with photos, eating out, orders, ~70 days of history) and
routes HTTP requests to the actual view handlers, so frontend and backend
changes can be tried in a browser without a Home Assistant instance.

    python dev/mock_server.py          # http://localhost:8124
    MOCK_PORT=9000 python dev/mock_server.py

  /                       the panel (frontend/index.html)
  /dev/cards.html         the Lovelace cards on a stand-in dashboard
  /api/meal_planner/...   the real API views

Data is reseeded on every start and written to dev/.mock-data/ (git-ignored).
Only Python's standard library is needed.
"""
import asyncio
import json
import mimetypes
import os
import re
import struct
import sys
import types
import zlib
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DEV = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(DEV)
CONFIG = os.path.join(DEV, ".mock-data")
FRONTEND = os.path.join(REPO, "custom_components", "meal_planner", "frontend")
PORT = int(os.environ.get("MOCK_PORT", "8124"))


# ── Stubs ────────────────────────────────────────────────────────────────
class Response:
    def __init__(self, body=None, status=200, content_type="application/json", headers=None, text=None):
        if text is not None:
            body = text.encode()
        self.body = body if isinstance(body, bytes) else (body or b"")
        self.status = status
        self.content_type = content_type
        self.headers = headers or {}


class HTTPServiceUnavailable(Exception):
    def __init__(self, text=""):
        super().__init__(text)


aiohttp = types.ModuleType("aiohttp")
aiohttp.web = types.SimpleNamespace(
    Response=Response, Request=object, HTTPServiceUnavailable=HTTPServiceUnavailable
)
sys.modules["aiohttp"] = aiohttp


def mod(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules[name] = m
    return m


class HomeAssistantView:
    def json(self, result, status_code=200):
        return Response(json.dumps(result).encode(), status_code)

    def json_message(self, message, status_code=200):
        return self.json({"message": message}, status_code)


class ConfigEntry:
    def __class_getitem__(cls, item):
        return cls


class ConfigEntryState:
    LOADED = "loaded"


mod("homeassistant")
mod("homeassistant.components")
mod("homeassistant.components.frontend", async_register_built_in_panel=None, async_remove_panel=None)
mod("homeassistant.components.http", HomeAssistantView=HomeAssistantView, StaticPathConfig=None)
mod("homeassistant.helpers")
mod("homeassistant.helpers.aiohttp_client", async_get_clientsession=None)
mod("homeassistant.config_entries", ConfigEntry=ConfigEntry, ConfigEntryState=ConfigEntryState)
mod("homeassistant.core", HomeAssistant=object)
mod("homeassistant.helpers.event", async_track_time_change=None)


class Store:
    async def async_save(self, data):
        with open(os.path.join(CONFIG, "store.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)


mod("homeassistant.helpers.storage", Store=Store)

sys.dont_write_bytecode = True  # keep the repo free of __pycache__
sys.path.insert(0, REPO)
from custom_components import meal_planner as mp  # noqa: E402


# ── Demo images (pure-python PNG) ────────────────────────────────────────
def png(path, w, h, fn):
    rows = b"".join(b"\x00" + bytes(c for x in range(w) for c in fn(x, y)) for y in range(h))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)


def make_images(img_dir):
    os.makedirs(img_dir, exist_ok=True)
    specs = {
        "pasta.png": lambda x, y: (230, 120 + (x * 3 + y) % 90, 40),
        "curry.png": lambda x, y: (200 + (y % 40), 150, 20 + (x % 60)),
        "salad.png": lambda x, y: (60 + (x % 50), 190 + (y % 50), 70),
        "pizza.png": lambda x, y: (220, 60 + ((x // 12 + y // 12) % 2) * 120, 50),
        "luigi.png": lambda x, y: (120 + (x % 80), 40, 160 + (y % 80)),
        "order.png": lambda x, y: (40 + (y % 60), 110 + (x % 70), 220),
    }
    for name, fn in specs.items():
        png(os.path.join(img_dir, name), 96, 96, fn)


# ── Seed data ────────────────────────────────────────────────────────────
def seed():
    today = date.today()
    d = lambda off: (today + timedelta(days=off)).isoformat()
    data = mp._default_data()
    img = {"Spaghetti Bolognese": "pasta.png", "Hähnchen-Curry": "curry.png",
           "Griechischer Salat mit Fladenbrot": "salad.png", "Pizza Margherita": "pizza.png"}
    for dish in data["dishes"]:
        dish["image"] = img.get(dish["name"])
    by = {x["name"]: x for x in data["dishes"]}

    def dish(name):
        return {"type": "dish", "dish_id": by[name]["id"], "dish_name": name}

    plan = {}
    names = [x["name"] for x in data["dishes"]]
    # ~70 days of history for the statistics
    for off in range(-75, -2):
        k = off % 9
        if k == 0:
            plan[d(off)] = {"type": "eating_out", "dish_name": ["Pizzeria Luigi", "Sushi Bar", "Beim Griechen"][off % 3]}
        elif k == 4:
            plan[d(off)] = {"type": "order", "dish_name": ["Lieferando", ""][off % 2]}
        elif k == 7:
            plan[d(off)] = {"type": "nothing", "dish_name": ""}
        else:
            plan[d(off)] = dish(names[(off * 7) % 12])
    plan[d(-2)] = dish("Spaghetti Bolognese")
    plan[d(-1)] = {"type": "eating_out", "dish_name": "Pizzeria Luigi"}
    plan[d(0)] = dish("Hähnchen-Curry")
    plan[d(1)] = dish("Griechischer Salat mit Fladenbrot")
    plan[d(2)] = {"type": "order", "dish_name": ""}
    plan[d(3)] = {"type": "nothing", "dish_name": ""}
    plan[d(4)] = dish("Pizza Margherita")
    plan[d(5)] = {"type": "eating_out", "dish_name": "Sushi Bar"}
    plan[d(6)] = {"type": "custom", "dish_name": "Omas Rouladen"}
    plan[d(8)] = dish("Spaghetti Bolognese")
    data["meal_plan"] = plan
    data["places"] = [
        {"id": "p-luigi", "type": "eating_out", "name": "Pizzeria Luigi", "image": "luigi.png"},
        {"id": "p-order", "type": "order", "name": "", "image": "order.png"},
    ]
    mp._recompute_dish_usage(data)
    return data


os.makedirs(CONFIG, exist_ok=True)
make_images(os.path.join(CONFIG, mp.IMAGE_DIR_NAME))
DATA = seed()


class FakeEntry:
    state = ConfigEntryState.LOADED
    options = {"lang": "de"}
    runtime_data = mp.MealPlannerRuntimeData(store=Store(), data=DATA)


async def _executor(fn, *args):
    return fn(*args)


hass = types.SimpleNamespace(
    config_entries=types.SimpleNamespace(async_entries=lambda domain: [FakeEntry]),
    async_add_executor_job=_executor,
    config=types.SimpleNamespace(path=lambda name: os.path.join(CONFIG, name)),
)

VIEWS = []
for cls in (mp.MealPlannerDishesView, mp.MealPlannerDishView, mp.MealPlannerDishImageView,
            mp.MealPlannerPlacesView, mp.MealPlannerPlaceImageView, mp.MealPlannerPlanView,
            mp.MealPlannerDayView, mp.MealPlannerMoveView, mp.MealPlannerSuggestView,
            mp.MealPlannerRejectView, mp.MealPlannerUnblockView, mp.MealPlannerHistoryCSVView,
            mp.MealPlannerSettingsView, mp.MealPlannerStatsView):
    pattern = "^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", cls.url) + "$"
    VIEWS.append((re.compile(pattern), cls(hass)))


class FakeRequest:
    def __init__(self, body, content_type, query):
        self._body, self.content_type, self.query = body, content_type, query

    async def json(self):
        return json.loads(self._body.decode() or "null")

    async def read(self):
        return self._body


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    def _send(self, status, body, ctype, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _file(self, base, rel):
        path = os.path.normpath(os.path.join(base, rel))
        if not path.startswith(base) or not os.path.isfile(path):
            return self._send(404, b"not found", "text/plain")
        with open(path, "rb") as f:
            self._send(200, f.read(), mimetypes.guess_type(path)[0] or "application/octet-stream")

    def _route(self):
        u = urlparse(self.path)
        if u.path.startswith("/dev/"):
            return self._file(DEV, u.path.split("/", 2)[2])
        if u.path == "/meal_planner_frontend/meal-planner-card.js":
            return self._file(FRONTEND, "meal-planner-card.js")
        if u.path.startswith("/meal_planner_images/"):
            return self._file(os.path.join(CONFIG, mp.IMAGE_DIR_NAME), u.path.split("/", 2)[2])
        if u.path == "/api/meal_planner/holidays":
            # Fake holidays: one weekday, one on a weekend
            t = date.today()
            return self._send(200, json.dumps({
                (t + timedelta(days=9)).isoformat(): "Test-Feiertag",
                (t + timedelta(days=(5 - t.weekday()) % 7 + 7)).isoformat(): "Test-Feiertag am Samstag",
            }).encode(), "application/json")
        if u.path.startswith("/api/"):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
            query = {k: v[0] for k, v in parse_qs(u.query).items()}
            for rx, view in VIEWS:
                m = rx.match(u.path)
                if m and hasattr(view, self.command.lower()):
                    handler = getattr(view, self.command.lower())
                    resp = asyncio.run(handler(FakeRequest(body, ctype, query), **m.groupdict()))
                    return self._send(resp.status, resp.body, resp.content_type, resp.headers)
            return self._send(404, b"no route", "text/plain")
        rel = u.path.lstrip("/") or "index.html"
        return self._file(FRONTEND, rel)

    do_GET = do_POST = do_DELETE = do_PATCH = _route


if __name__ == "__main__":
    print(f"mock on http://localhost:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
