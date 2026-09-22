DOMAIN = "meal_planner"
STORAGE_KEY = "meal_planner"
STORAGE_VERSION = 1

PANEL_URL = "meal-planner"
PANEL_TITLE = "Meal Planner"
PANEL_ICON = "mdi:silverware-fork-knife"

DEFAULT_DISHES = [
    "Spaghetti Bolognese",
    "Hähnchen-Curry",
    "Gemüsepfanne",
    "Schnitzel mit Pommes",
    "Pizza Margherita",
    "Lasagne",
    "Gulasch",
    "Rinderbraten",
    "Tortellini in Tomatensoße",
    "Griechischer Salat mit Fladenbrot",
    "Tacos",
    "Burger",
    "Gebratener Reis",
    "Nudeln mit Pesto",
    "Shakshuka",
    "Linsensuppe",
    "Minestrone",
    "Flammkuchen",
    "Käsespätzle",
    "Chili con Carne",
    "Wraps mit Hähnchen",
    "Fischstäbchen mit Kartoffelbrei",
    "Grillgemüse mit Couscous",
    "Risotto",
    "Gnocchi in Salbeibutter",
    "Pfannkuchen",
    "Ofenkartoffeln",
    "Quiche Lorraine",
    "Gemüsesuppe",
    "Ramen",
    "Pad Thai",
    "Pulled Pork",
    "Lachsfilet mit Reis",
    "Chicken Tikka Masala",
    "Burritos",
    "Drahde Wixpfeiferl",
    "Boeuf a la boeuf",
    "Schwammerlbrühe",
    "Pizzaleberkas",
]

# Day plan types
TYPE_DISH = "dish"
TYPE_EATING_OUT = "eating_out"
TYPE_ORDER = "order"
TYPE_NOTHING = "nothing"
TYPE_CUSTOM = "custom"

# Dish photos — stored in the config dir, served as static files
IMAGE_DIR_NAME = "meal_planner_images"
IMAGE_URL_BASE = "/meal_planner_images"
MAX_IMAGE_BYTES = 3 * 1024 * 1024  # generous: the panel downscales before upload
IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# Config option keys
CONF_LANG = "lang"
CONF_HOLIDAY_COUNTRY = "holiday_country"
CONF_HOLIDAY_STATE = "holiday_state"

# Supported holiday countries (subset of python-holidays)
HOLIDAY_COUNTRIES = {
    "": "Aus",
    "DE": "Deutschland",
    "AT": "Österreich",
    "CH": "Schweiz",
}

# German federal states (ISO 3166-2 subdivisions used by python-holidays)
HOLIDAY_STATES_DE = {
    "": "Nur bundesweite Feiertage",
    "BW": "Baden-Württemberg",
    "BY": "Bayern",
    "BE": "Berlin",
    "BB": "Brandenburg",
    "HB": "Bremen",
    "HH": "Hamburg",
    "HE": "Hessen",
    "MV": "Mecklenburg-Vorpommern",
    "NI": "Niedersachsen",
    "NW": "Nordrhein-Westfalen",
    "RP": "Rheinland-Pfalz",
    "SL": "Saarland",
    "SN": "Sachsen",
    "ST": "Sachsen-Anhalt",
    "SH": "Schleswig-Holstein",
    "TH": "Thüringen",
}
