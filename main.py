"""FastAPI app: 4 API endpoints + serves the mobile web page.

Run:  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Public phone link:  ngrok http 8000
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import vlm

app = FastAPI(title="Menu Decoder")

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic"}


@app.post("/api/menu")
async def scan_menu(image: UploadFile = File(...), target_lang: str = Form("English")):
    """Batch pass: menu photo -> tier-1 cards for every dish."""
    if image.content_type not in ALLOWED_MIME:
        raise HTTPException(415, f"Unsupported image type: {image.content_type}")
    data = await image.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Image too large (max 10 MB)")
    try:
        result = vlm.read_menu(data, image.content_type, target_lang)
    except Exception as e:
        raise HTTPException(502, f"Model error: {e}")
    if not result.dishes:
        raise HTTPException(422, "No dishes found - try a clearer photo")
    return result


class DishRequest(BaseModel):
    name: str
    language: str = "unknown"
    target_lang: str = "English"


@app.post("/api/dish")
async def dish_detail(req: DishRequest):
    """Lazy pass: one dish name -> tier-2 detail."""
    try:
        return vlm.explain_dish(req.name, req.language, req.target_lang)
    except Exception as e:
        raise HTTPException(502, f"Model error: {e}")


class RegionRequest(BaseModel):
    region: str
    target_lang: str = "English"


@app.post("/api/region")
async def region_detail(req: RegionRequest):
    """Food culture of a region, fetched when the user taps Explore."""
    try:
        return vlm.region_info(req.region, req.target_lang)
    except Exception as e:
        raise HTTPException(502, f"Model error: {e}")


class CityRequest(BaseModel):
    city: str
    target_lang: str = "English"


@app.post("/api/city")
async def city_detail(req: CityRequest):
    """Must-try dish guide for a travel destination."""
    if not req.city.strip():
        raise HTTPException(422, "City name is empty")
    try:
        return vlm.city_guide(req.city.strip(), req.target_lang)
    except Exception as e:
        raise HTTPException(502, f"Model error: {e}")


class StoryRequest(BaseModel):
    name: str
    canonical: str = ""
    target_lang: str = "English"


@app.post("/api/story")
async def story_detail(req: StoryRequest):
    """Deeper heritage story, fetched when the user taps Tell me more."""
    try:
        return vlm.story_deep(req.name, req.canonical or req.name, req.target_lang)
    except Exception as e:
        raise HTTPException(502, f"Model error: {e}")


class IngredientRequest(BaseModel):
    name: str
    target_lang: str = "English"


@app.post("/api/ingredient")
async def ingredient_detail(req: IngredientRequest):
    """Quick ingredient primer, fetched when a chip is tapped."""
    try:
        return vlm.ingredient_info(req.name, req.target_lang)
    except Exception as e:
        raise HTTPException(502, f"Model error: {e}")


app.mount("/", StaticFiles(directory="static", html=True), name="static")