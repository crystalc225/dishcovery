"""All OpenAI calls live here."""
import os
import base64
import json
from dotenv import load_dotenv
from openai import OpenAI
from schema import MenuResult, DishTier2, RegionInfo, CityGuide, StoryDeep, IngredientInfo

load_dotenv()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"


def _chat_json(content, max_tokens):
    """Shared call wrapper: forces JSON, parses it."""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"},
        max_tokens=max_tokens,
    )
    return json.loads(resp.choices[0].message.content)


MENU_PROMPT = """You are reading a photo of a restaurant menu. The menu may be in any language.

Extract every dish you can read. Return a JSON object matching this exact schema:
{{
  "detected_language": "string (e.g. Thai, Japanese, Chinese)",
  "dishes": [
    {{
      "original": "dish name exactly as printed in original script",
      "translated_name": "the name a local English-language menu would actually print. Prefer the internationally recognized romanized name plus a short descriptor, e.g. Pad Krapow (basil pork rice), Mapo Tofu, Lu Rou Fan (braised pork rice). Avoid stiff word-for-word translations.",
      "literal": "word-for-word translation ONLY if it differs amusingly or confusingly from what the dish is, otherwise null",
      "what_it_is": "one short plain-{target_lang} line saying what the dish actually is. Interpret, do not just translate.",
      "category": "main / side / soup / cold_dish / dessert / drink / other",
      "confidence": "known if you recognize this as a real dish, unsure if guessing"
    }}
  ]
}}

Rules:
- Never invent facts. If unsure, set confidence to unsure and keep what_it_is conservative.
- Skip prices, section headers, and non-dish items.
- Return ONLY the JSON object."""

DISH_PROMPT = """The dish is: {name}
Menu language: {language}

Explain this dish for a traveler in {target_lang}. Return a JSON object with exactly these fields:
{{
  "spice": 0,
  "texture": "e.g. chewy and gelatinous",
  "temperature": "hot / cold / room",
  "contains_offal": false,
  "common_allergens": ["shellfish"],
  "key_ingredients": ["3-6 main ingredients"],
  "eaten_when": "when it is traditionally eaten: everyday lunch? festivals? late-night? winter warmer?",
  "seasonal": "year-round, or the season it belongs to and why",
  "how_to_eat": "practical advice e.g. shared dish eaten over rice",
  "heritage": "2-4 sentences a traveler would love: history, tradition, who eats it and when. Real facts only - if you don't know its history, say it is a common everyday dish and describe how it is enjoyed.",
  "english_name": "common English name, e.g. Mapo Tofu",
  "canonical_name": "the single most internationally searchable name for this dish, usually the romanized local name, e.g. Pad kaprao, Lu rou fan, Mapo doufu",
  "origin_region": "region most associated with it, e.g. Sichuan, China",
  "origin_lat": 30.6,
  "origin_lng": 104.1,
  "confidence": "known or unsure"
}}
spice is an integer 0-3. If unsure about the dish, set confidence to unsure and keep every field conservative.
Return ONLY the JSON object."""

REGION_PROMPT = """Region: {region}

Write a short food-culture guide to this region for a curious traveler, in {target_lang}.
Return a JSON object with exactly these fields:
{{
  "region": "{region}",
  "overview": "2-3 sentences about the region itself - geography, character",
  "food_culture": "2-4 sentences on how people here eat: flavors they love, meal rhythms, cooking styles",
  "signature_ingredients": ["4-7 ingredients this region is known for"],
  "must_try": ["4-6 other famous dishes from this region, each as 'Original name - English name'"]
}}
Real facts only. Return ONLY the JSON object."""

CITY_PROMPT = """City: {city}

Create a must-try local food guide for a traveler visiting this city, in {target_lang}.
Return a JSON object with exactly these fields:
{{
  "city": "{city}",
  "lat": 0.0,
  "lng": 0.0,
  "intro": "2-3 sentences on this city's food identity",
  "customs": "2-3 sentences of local eating customs and etiquette a visitor should know",
  "dishes": [
    {{
      "name_original": "dish name in the local language",
      "name_english": "English name",
      "why": "one line on why it is a must-try here specifically",
      "where_to_find": "the TYPE of place: night markets, breakfast shops, old town alleys",
      "price_range": "typical price in the local currency, e.g. NT$50-80",
      "famous_spots": ["ONLY institutions genuinely famous for this dish that you are confident actually exist (e.g. Din Tai Fung for xiaolongbao). If none are famous enough to be certain, return an empty list. NEVER invent a name."],
      "local_tip": "how locals order or eat it"
    }}
  ]
}}
lat/lng are the city's approximate center coordinates.
Include 5-8 dishes. For famous_spots, accuracy matters more than completeness - an empty list is always better than a guessed name.
Real dishes only, genuinely local to this city or its region. Return ONLY the JSON object."""


def read_menu(image_bytes: bytes, mime_type: str, target_lang: str = "English") -> MenuResult:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data = _chat_json([
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
        {"type": "text", "text": MENU_PROMPT.format(target_lang=target_lang)},
    ], max_tokens=2500)
    return MenuResult(**data)


def explain_dish(name: str, language: str, target_lang: str = "English") -> DishTier2:
    data = _chat_json(DISH_PROMPT.format(name=name, language=language, target_lang=target_lang), max_tokens=900)
    return DishTier2(**data)


def region_info(region: str, target_lang: str = "English") -> RegionInfo:
    data = _chat_json(REGION_PROMPT.format(region=region, target_lang=target_lang), max_tokens=700)
    return RegionInfo(**data)


def city_guide(city: str, target_lang: str = "English") -> CityGuide:
    data = _chat_json(CITY_PROMPT.format(city=city, target_lang=target_lang), max_tokens=1400)
    return CityGuide(**data)


STORY_PROMPT = """Dish: {name} ({canonical})

Write a deeper food-history piece about this dish for a curious traveler, in {target_lang}.
Return a JSON object: {{"story": "2-3 short paragraphs separated by \\n\\n"}}
Cover: where and how it originated, how it spread or evolved, any story/legend (clearly marked as legend if unverified), regional variations, and how locals feel about it today.
Real facts only - if the history is thin, say so honestly and write about how it fits into daily eating culture instead.
Return ONLY the JSON object."""


INGREDIENT_PROMPT = """Ingredient: {name}

Give a traveler a quick primer on this ingredient, in {target_lang}.
Return a JSON object with exactly these fields:
{{
  "name": "{name}",
  "overview": "1-2 sentences: what it is, where it comes from",
  "tastes_like": "one line describing flavor/aroma",
  "used_in": ["3-5 well-known dishes or uses"]
}}
Return ONLY the JSON object."""


def story_deep(name: str, canonical: str, target_lang: str = "English") -> StoryDeep:
    data = _chat_json(STORY_PROMPT.format(name=name, canonical=canonical, target_lang=target_lang), max_tokens=800)
    return StoryDeep(**data)


def ingredient_info(name: str, target_lang: str = "English") -> IngredientInfo:
    data = _chat_json(INGREDIENT_PROMPT.format(name=name, target_lang=target_lang), max_tokens=400)
    return IngredientInfo(**data)