"""Data contract. Everything else depends on these shapes."""
from pydantic import BaseModel


class DishTier1(BaseModel):
    original: str               # dish name exactly as printed, original script
    translated_name: str        # natural name in target language, e.g. "Braised Eggplant in Garlic Sauce"
    literal: str | None = None  # literal translation only if amusingly/confusingly different
    what_it_is: str             # one-line plain answer
    image_query: str            # generic dish type for photo search, e.g. "cheeseburger" - never a brand/marketing name
    category: str               # main / side / soup / cold_dish / dessert / drink / other
    confidence: str             # "known" or "unsure"


class MenuResult(BaseModel):
    detected_language: str
    dishes: list[DishTier1]


class DishTier2(BaseModel):
    spice: int                  # 0-3
    texture: str
    temperature: str            # hot / cold / room
    contains_offal: bool
    common_allergens: list[str]
    key_ingredients: list[str]  # 3-6 main ingredients
    eaten_when: str             # breakfast? festivals? late-night? everyday?
    seasonal: str               # "year-round" or the season and why
    how_to_eat: str
    heritage: str               # 2-4 sentences: history, tradition
    english_name: str           # common English name
    canonical_name: str         # internationally searchable name, e.g. "Pad kaprao" - used for photo search
    origin_region: str          # e.g. "Sichuan, China"
    origin_lat: float
    origin_lng: float
    confidence: str


class RegionInfo(BaseModel):
    """Food culture of a region, fetched when the user taps Explore."""
    region: str
    overview: str               # 2-3 sentences about the region itself
    food_culture: str           # 2-4 sentences on how people there eat
    signature_ingredients: list[str]
    must_try: list[str]         # 4-6 other famous dishes from this region


class CityDish(BaseModel):
    name_original: str
    name_english: str
    why: str                    # why it's a must-try, one line
    where_to_find: str          # e.g. "night markets", "breakfast shops"
    price_range: str            # typical price in local currency, e.g. "NT$50-80"
    famous_spots: list[str]     # ONLY genuinely famous, verifiable places; empty if none
    local_tip: str              # how locals order/eat it


class CityGuide(BaseModel):
    city: str
    lat: float                  # city center coords for the map
    lng: float
    intro: str                  # 2-3 sentences on the city's food identity
    customs: str                # 2-3 sentences of local eating etiquette/customs
    dishes: list[CityDish]      # 5-8 must-try dishes


class StoryDeep(BaseModel):
    """Longer heritage deep-dive, fetched when the user taps Tell me more."""
    story: str                  # 2-3 short paragraphs


class IngredientInfo(BaseModel):
    """Quick primer on one ingredient, fetched when a chip is tapped."""
    name: str
    overview: str               # 1-2 sentences: what it is
    tastes_like: str            # one line
    used_in: list[str]          # 3-5 dishes/uses
